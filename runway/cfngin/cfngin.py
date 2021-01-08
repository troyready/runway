"""CFNgin entrypoint."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from yaml.constructor import ConstructorError

from runway._logging import PrefixAdaptor
from runway.util import MutableMap, SafeHaven, cached_property

from ..config import CfnginConfig
from .actions import build, destroy, diff
from .context import Context as CFNginContext
from .environment import parse_environment
from .providers.aws.default import ProviderBuilder

if TYPE_CHECKING:
    from ..context import Context as RunwayContext

# explicitly name logger so its not redundant
LOGGER = logging.getLogger("runway.cfngin")


class CFNgin:
    """Control CFNgin.

    Attributes:
        concurrency (int): Max number of CFNgin stacks that can be deployed
            concurrently. If the value is ``0``, will be constrained based on
            the underlying graph.
        interactive (bool): Whether or not to prompt the user before taking
            action.
        parameters (MutableMap): Combination of the parameters provided when
            initalizing the class and any environment files that are found.
        recreate_failed (bool): Destroy and re-create stacks that are stuck in
            a failed state from an initial deployment when updating.
        region (str): The AWS region where CFNgin is currently being executed.
        sys_path (str): Working directory.
        tail (bool): Whether or not to display all CloudFormation events in the
            terminal.

    """

    def __init__(
        self,
        ctx: RunwayContext,
        parameters: Optional[Dict[str, Any]] = None,
        sys_path: Optional[Path] = Path.cwd(),
    ) -> None:
        """Instantiate class.

        Args:
            ctx: Runway context object.
            parameters: Parameters from Runway.
            sys_path: Working directory.

        """
        self.__ctx = ctx
        self._env_file_name = None
        self.concurrency = ctx.env.max_concurrent_cfngin_stacks
        self.interactive = ctx.is_interactive
        self.parameters = MutableMap()
        self.recreate_failed = ctx.is_noninteractive
        self.region = ctx.env_region
        self.sys_path = sys_path if isinstance(sys_path, Path) else Path(sys_path)
        self.tail = bool(ctx.env.debug or ctx.env.verbose)

        self.parameters.update(self.env_file)

        if parameters:
            LOGGER.debug("adding Runway parameters to CFNgin parameters")
            self.parameters.update(parameters)

        self._inject_common_parameters()

    @cached_property
    def env_file(self) -> MutableMap:
        """Contents of a CFNgin environment file."""
        result = {}
        supported_names = [
            "{}.env".format(self.__ctx.env_name),
            "{}-{}.env".format(self.__ctx.env_name, self.region),
        ]
        for _, file_name in enumerate(supported_names):
            file_path = os.path.join(self.sys_path, file_name)
            if os.path.isfile(file_path):
                LOGGER.info("found environment file: %s", file_path)
                self._env_file_name = file_path
                with open(file_path, "r") as file_:
                    result.update(parse_environment(file_.read()))
        return MutableMap(**result)

    def deploy(self, force: bool = False, sys_path: Optional[Path] = None) -> None:
        """Run the CFNgin deploy action.

        Args:
            force: Explicitly enable the action even if an environment
                file is not found.
            sys_path: Explicitly define a path to work in.
                If not provided, ``self.sys_path`` is used.

        """
        if self.should_skip(force):
            return
        if not sys_path:
            sys_path = self.sys_path
        config_file_paths = self.find_config_files(sys_path=sys_path)

        with SafeHaven(
            environ=self.__ctx.env_vars, sys_modules_exclude=["awacs", "troposphere"]
        ):
            for config_path in config_file_paths:
                logger = PrefixAdaptor(os.path.basename(config_path), LOGGER)
                logger.notice("deploy (in progress)")
                with SafeHaven(
                    argv=["stacker", "build", str(config_path)],
                    sys_modules_exclude=["awacs", "troposphere"],
                ):
                    ctx = self.load(config_path)
                    action = build.Action(
                        context=ctx,
                        provider_builder=self._get_provider_builder(
                            ctx.config.service_role
                        ),
                    )
                    action.execute(concurrency=self.concurrency, tail=self.tail)
                logger.success("deploy (complete)")

    def destroy(self, force: bool = False, sys_path: Optional[Path] = None) -> None:
        """Run the CFNgin destroy action.

        Args:
            force: Explicitly enable the action even if an environment
                file is not found.
            sys_path: Explicitly define a path to work in.
                If not provided, ``self.sys_path`` is used.

        """
        if self.should_skip(force):
            return
        if not sys_path:
            sys_path = self.sys_path
        config_file_paths = self.find_config_files(sys_path=sys_path)
        # destroy should run in reverse to handle dependencies
        config_file_paths.reverse()

        with SafeHaven(environ=self.__ctx.env_vars):
            for config_path in config_file_paths:
                logger = PrefixAdaptor(config_path.name, LOGGER)
                logger.notice("destroy (in progress)")
                with SafeHaven(argv=["stacker", "destroy", str(config_path)]):
                    ctx = self.load(config_path)
                    action = destroy.Action(
                        context=ctx,
                        provider_builder=self._get_provider_builder(
                            ctx.config.service_role
                        ),
                    )
                    action.execute(
                        concurrency=self.concurrency, force=True, tail=self.tail
                    )
                logger.success("destroy (complete)")

    def load(self, config_path: Path) -> CFNginContext:
        """Load a CFNgin config into a context object.

        Args:
            config_path: Valid path to a CFNgin config file.

        """
        LOGGER.debug("loading CFNgin config: %s", config_path.name)
        try:
            config = self._get_config(config_path)
            config.load()
            return self._get_context(config, config_path)
        except ConstructorError as err:
            if err.problem.startswith(
                "could not determine a constructor " "for the tag '!"
            ):
                LOGGER.error(
                    '"%s" is located in the module\'s root directory '
                    "and appears to be a CloudFormation template; "
                    "please move CloudFormation templates to a subdirectory",
                    config_path,
                )
                sys.exit(1)
            raise

    def plan(self, force: bool = False, sys_path: Optional[Path] = None):
        """Run the CFNgin plan action.

        Args:
            force: Explicitly enable the action even if an environment
                file is not found.
            sys_path: Explicitly define a path to work in.
                If not provided, ``self.sys_path`` is used.

        """
        if self.should_skip(force):
            return
        if not sys_path:
            sys_path = self.sys_path
        config_file_paths = self.find_config_files(sys_path=sys_path)
        with SafeHaven(environ=self.__ctx.env_vars):
            for config_path in config_file_paths:
                logger = PrefixAdaptor(config_path.name, LOGGER)
                logger.notice("plan (in progress)")
                with SafeHaven(argv=["stacker", "diff", str(config_path)]):
                    ctx = self.load(config_path)
                    action = diff.Action(
                        context=ctx,
                        provider_builder=self._get_provider_builder(
                            ctx.config.service_role
                        ),
                    )
                    action.execute()
                logger.success("plan (complete)")

    def should_skip(self, force: bool = False) -> bool:
        """Determine if action should be taken or not.

        Args:
            force (bool): If ``True``, will always return ``False`` meaning
                the action should not be skipped.

        Returns:
            bool: Skip action or not.

        """
        if force or self.env_file:
            return False
        LOGGER.info("skipped; no parameters and environment file not found")
        return True

    def _get_config(self, file_path: Path) -> CfnginConfig:
        """Initialize a CFNgin config object from a file.

        Args:
            file_path (str): Path to the config file to load.
            validate (bool): Validate the loaded config.

        """
        return CfnginConfig.parse_file(file_path=file_path, parameters=self.parameters)

    def _get_context(self, config: CfnginConfig, config_path: Path) -> CFNginContext:
        """Initialize a CFNgin context object.

        Args:
            config: CFNgin config object.
            config_path: Path to the config file that was provided.

        """
        return CFNginContext(
            boto3_credentials=self.__ctx.boto3_credentials,
            config=config,
            config_path=config_path,
            environment=self.parameters,
            force_stacks=[],  # placeholder
            region=self.region,
            stack_names=[],  # placeholder
        )

    def _get_provider_builder(
        self, service_role: Optional[str] = None
    ) -> ProviderBuilder:
        """Initialize provider builder.

        Args:
            service_role: CloudFormation service role.

        """
        if self.interactive:
            LOGGER.verbose("using interactive AWS provider mode")
        else:
            LOGGER.verbose("using default AWS provider mode")
        return ProviderBuilder(
            interactive=self.interactive,
            recreate_failed=self.recreate_failed,
            region=self.region,
            service_role=service_role,
        )

    def _inject_common_parameters(self) -> None:
        """Add common parameters if they don't already exist.

        Adding these commonly used parameters will remove the need to add
        lookup support (mainly for environment variable lookups) in places
        such as ``cfngin_bucket``.

        Injected Parameters
        ~~~~~~~~~~~~~~~~~~~

        **environment (str)**
            Taken from the ``DEPLOY_ENVIRONMENT`` environment variable. This
            will the be current Runway environment being processed.

        **region (str)**
            Taken from the ``AWS_REGION`` environment variable. This will be
            the current region being deployed to.

        """
        if not self.parameters.get("environment"):
            self.parameters["environment"] = self.__ctx.env_name
        if not self.parameters.get("region"):
            self.parameters["region"] = self.region

    @classmethod
    def find_config_files(
        cls, exclude: Optional[List[str]] = None, sys_path: Optional[Path] = None
    ) -> List[Path]:
        """Find CFNgin config files.

        Args:
            exclude: List of file names to exclude. This list is appended to
                the global exclude list.
            sys_path: Explicitly define a path to search for config files.

        Returns:
            Paths to config files that were found.

        """
        return CfnginConfig.find_config_file(sys_path, exclude=exclude)
