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


class RuntestMetadata(Metadata):
    """
    Metadata implementation to handle a LTP runtest file.
    """

    def __init__(self, basedir: str) -> None:
        """
        :param basedir: directory where runtest files are stored
        :type basedir: str
        """
        self._logger = logging.getLogger("ltp.metadata.runtest")
        self._basedir = basedir

    def _read_suite_impl(self, name: str):
        self._logger.info("Collecting testing suite: %s", name)

        suite_path = os.path.join(self._basedir, name)

        if not os.path.isfile(suite_path):
            raise MetadataError(f"Testing suite doesn't exist in {suite_path}")

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
                raise MetadataError(
                    "Test declaration is not defining the command")

            test_data = dict(
                name=parts[0],
                command=parts[1],
                arguments=[]
            )

            if len(parts) >= 3:
                test_data["arguments"] = parts[2:]

            tests.append(test_data)

            self._logger.debug("test data: %s", test_data)

        self._logger.debug("Collected %d tests", len(tests))

        suite_data = {
            "name": name,
            "tests": tests
        }

        self._logger.debug(suite_data)
        self._logger.info("Collected testing suite")

        return suite_data
