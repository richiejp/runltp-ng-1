"""
.. module:: json
    :platform: Linux
    :synopsis: json format exporter

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import json
import logging
from ltp.backend import Backend
from ltp.runner import Runner
from .base import Exporter
from .base import ExporterError


class JSONExporter(Exporter):
    """
    Export testing results into a JSON file.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("ltp.results.json")

    @staticmethod
    def _read_sut_info(runner: Runner, cmd) -> str:
        """
        Read SUT information using command runner.
        """
        ret = runner.run_cmd(cmd, 10)
        if ret["returncode"] != 0:
            raise ExporterError(f"Can't read information from SUT: {cmd}")

        stdout = ret["stdout"].rstrip()

        return stdout

    # pylint: disable=too-many-locals
    def save_file(
            self,
            backend: Backend,
            results: list,
            path: str) -> None:
        if not backend:
            raise ValueError("backend is None")

        if not results:
            raise ValueError("results is empty")

        if not path:
            raise ValueError("path is empty")

        if os.path.exists(path):
            raise ExporterError(f"'{path}' already exists")

        self._logger.info("Exporting JSON report into %s", path)

        data = {}

        # read backend information
        # TODO: memory? disk?
        _, runner = backend.communicate()

        distro_str = self._read_sut_info(
            runner, ". /etc/os-release; echo \"$ID\"")
        distro_ver_str = self._read_sut_info(
            runner, ". /etc/os-release; echo \"$VERSION_ID\"")
        kernel_str = self._read_sut_info(
            runner, "uname -s -r -v")
        arch_str = self._read_sut_info(
            runner, "uname -m")

        data["sut"] = {
            "distro": distro_str,
            "distro_ver": distro_ver_str,
            "kernel": kernel_str,
            "arch": arch_str,
        }

        # add results information
        data_suites = []

        for result in results:
            data_suite = {}
            data_suite["name"] = result.suite.name
            data_suite["results"] = {
                "exec_time": result.exec_time,
                "failed": result.failed,
                "passed": result.passed,
                "broken": result.broken,
                "skipped": result.skipped,
                "warnings": result.warnings
            }

            data_tests = []
            for test_report in result.tests_results:
                data_test = {}
                data_test["name"] = test_report.test.name
                data_test["command"] = test_report.test.command
                data_test["arguments"] = test_report.test.arguments
                data_test["stdout"] = test_report.stdout
                data_test["returncode"] = test_report.return_code
                data_test["exec_time"] = test_report.exec_time
                data_test["failed"] = test_report.failed
                data_test["passed"] = test_report.passed
                data_test["broken"] = test_report.broken
                data_test["skipped"] = test_report.skipped
                data_test["warnings"] = test_report.warnings
                data_tests.append(data_test)

            data_suite["tests"] = data_tests
            data_suites.append(data_suite)

        data["suites"] = data_suites

        with open(path, "w+", encoding='UTF-8') as outfile:
            json.dump(data, outfile, indent=4)

        self._logger.info("Report exported")
