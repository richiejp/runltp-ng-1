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

    def __init__(self, folder: str) -> None:
        """
        :param folder: runtest LTP folder
        :type folder: str
        """
        self._logger = logging.getLogger("ltp.metadata.runtest")
        self._suites = []
        self._avail_tests = []
        self._avail_suites = []
        self._collect(folder)

    def _collect(self, folder: str) -> dict:
        """
        Collect all the available testing suites.
        """
        self._logger.info("Collecting testing suites")

        suite_paths = [os.path.join(folder, fname)
                       for fname in os.listdir(folder)
                       if os.path.isfile(os.path.join(folder, fname))]

        self._logger.debug("suites paths: %s", suite_paths)

        # collect all testing suites
        self._suites.clear()

        for suite_path in suite_paths:
            suite_name = os.path.basename(suite_path)
            tests = []

            self._logger.info("Collecting '%s' suite tests", suite_name)

            lines = []
            with open(suite_path, "r", encoding='UTF-8') as data:
                lines = data.readlines()

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

                self._logger.debug("test data: %s", test_data)

                if len(parts) >= 3:
                    test_data["arguments"] = parts[2:]

                tests.append(test_data)

            self._logger.debug("Collected %d tests", len(tests))

            suite_data = {
                "name": suite_name,
                "tests": tests
            }
            self._suites.append(suite_data)

        # populate available suites and tests
        self._avail_suites = [suite["name"] for suite in self._suites]
        self._avail_tests.clear()

        for suite in self._suites:
            tests = [test["name"] for test in suite["tests"]]
            self._avail_tests.extend(tests)

        self._logger.info("Collected %d testing suites", len(self._suites))

    @property
    def available_suites(self):
        return self._avail_suites

    @property
    def available_tests(self):
        return self._avail_tests

    def _read_test_impl(self, name: str):
        if name not in self._avail_tests:
            raise ValueError(f"'{name}' test is not available")

        mytest = None
        for suite in self._suites:
            for test in suite["tests"]:
                if name == test["name"]:
                    mytest = test
                    break

            if mytest:
                break

        return mytest

    def _read_suite_impl(self, name: str):
        if name not in self._avail_suites:
            raise ValueError(f"'{name}' suite is not available")

        mysuite = None
        for suite in self._suites:
            if name == suite["name"]:
                mysuite = suite
                break

        return mysuite
