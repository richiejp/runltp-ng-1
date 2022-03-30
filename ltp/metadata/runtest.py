"""
.. module:: runtest.py
    :platform: Linux
    :synopsis: module handling runtest files metadata

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import logging
from .base import Metadata
from .base import MetadataError
from .base import Suite
from .base import Test


class RuntestMetadata(Metadata):
    """
    Metadata implementation to handle a LTP runtest file.
    """

    def __init__(self,) -> None:
        self._logger = logging.getLogger("ltp.metadata.runtest")

    def read_suite(self, suite_path: str) -> Suite:
        if not suite_path:
            raise ValueError("runtest file path is empty")

        if not os.path.isfile(suite_path):
            raise ValueError("runtest file doesn't exist")

        name = os.path.basename(suite_path)

        self._logger.info("Collecting testing suite: %s", name)

        lines = []
        try:
            with open(suite_path, "r", encoding='UTF-8') as data:
                lines = data.readlines()
        except IOError as err:
            raise MetadataError(err)

        tests = []
        for line in lines:
            if not line.strip() or line.strip().startswith("#"):
                continue

            self._logger.debug("test declaration: %s", line)

            parts = line.split()
            if len(parts) < 2:
                raise MetadataError("Test declaration is not defining command")

            test_name = parts[0]
            test_cmd = parts[1]
            test_args = []

            if len(parts) >= 3:
                test_args = parts[2:]

            test = Test(test_name, test_cmd, test_args)
            tests.append(test)

            self._logger.debug("test: %s", test)

        self._logger.debug("Collected %d tests", len(tests))

        suite = Suite(name, tests)

        self._logger.debug(suite)
        self._logger.info("Collected testing suite")

        return suite
