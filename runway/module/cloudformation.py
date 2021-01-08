"""Cloudformation module."""
import logging
import sys

from .. import cfngin as cfngin_module
from .. import variables
from .._logging import PrefixAdaptor
from ..cfngin.cfngin import CFNgin
from . import RunwayModule

LOGGER = logging.getLogger(__name__)

# TODO remove - https://github.com/onicagroup/runway/issues/293
sys.modules["stacker"] = cfngin_module  # shim to remove stacker dependency
sys.modules["stacker.variables"] = variables  # shim to support standard variables


class CloudFormation(RunwayModule):
    """CloudFormation (Stacker) Runway Module."""

    def __init__(self, context, path, options=None):
        """Instantiate class.

        Args:
            context (Context): Runway context object.
            path (Union[str, Path]): Path to the module.
            options (Dict[str, Dict[str, Any]]): Everything in the module
                definition merged with applicable values from the deployment
                definition.

        """
        super().__init__(context, path, options)
        # logger needs to be created here to use the correct logger
        self.logger = PrefixAdaptor(self.name, LOGGER)

    def deploy(self):
        """Run stacker build."""
        cfngin = CFNgin(
            self.context, parameters=self.options["parameters"], sys_path=self.path
        )
        cfngin.deploy(force=self.options["environment"])

    def destroy(self):
        """Run stacker destroy."""
        cfngin = CFNgin(
            self.context, parameters=self.options["parameters"], sys_path=self.path
        )
        cfngin.destroy(force=self.options["environment"])

    def plan(self):
        """Run stacker diff."""
        cfngin = CFNgin(
            self.context, parameters=self.options["parameters"], sys_path=self.path
        )
        cfngin.plan(force=self.options["environment"])
