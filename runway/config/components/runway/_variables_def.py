"""Runway config variables definition."""
from __future__ import annotations

import logging
from typing import Any, Dict

import yaml

from ....exceptions import VariablesFileNotFound
from ....util import MutableMap
from ...models.runway import RunwayVariablesDefinitionModel

LOGGER = logging.getLogger(__name__.replace("._", "."))


class RunwayVariablesDefinition(MutableMap):
    """Runway variables definition."""

    default_names = ["runway.variables.yml", "runway.variables.yaml"]

    # used to track persistent state on the class
    __has_notified_missing_file = False  # tracked to only log the message once

    def __init__(self, data: RunwayVariablesDefinitionModel) -> None:
        """Instantiate class."""
        # pylint: disable=protected-access
        self._file_path = data.file_path
        self._sys_path = data.sys_path
        data = RunwayVariablesDefinitionModel(**{**data.dict(), **self.__load_file()})
        super().__init__(**data.dict(exclude={"file_path", "sys_path"}))

    def __load_file(self) -> Dict[str, Any]:
        """Load a variables file."""
        # pylint: disable=protected-access
        if self._file_path:
            if self._file_path.is_file():
                return yaml.safe_load(self._file_path.read_text())
            raise VariablesFileNotFound(self._file_path.absolute())

        for name in self.default_names:
            test_path = self._sys_path / name
            LOGGER.debug("looking for variables file: %s", test_path)
            if test_path.is_file():
                LOGGER.verbose("found variables file: %s", test_path)
                return yaml.safe_load(test_path.read_text())

        if not self.__class__.__has_notified_missing_file:
            LOGGER.info(
                "could not find %s in the current directory; continuing without a variables file",
                " or ".join(self.default_names),
            )
            self.__class__.__has_notified_missing_file = True
        return {}

    @classmethod
    def parse_obj(cls, obj: Any) -> RunwayVariablesDefinition:
        """Parse a python object into this class.

        Args:
            obj: The object to parse.

        """
        return cls(RunwayVariablesDefinitionModel.parse_obj(obj))
