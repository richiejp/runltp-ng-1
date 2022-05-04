"""
.. module:: base
    :platform: Linux
    :synopsis: module containing Dispatcher definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import re
from ltp import LTPException
from ltp.metadata import Test
from ltp.results import TestResults


class DispatcherError(LTPException):
    """
    Raised when a error occurs during dispatcher operations.
    """


class Dispatcher:
    """
    A dispatcher that schedule jobs to run on target.
    """

    @staticmethod
    def _get_test_results(test: Test, test_data: dict) -> TestResults:
        """
        Return test results accoding with runner output and Test definition.
        :param test: Test definition object
        :type test: Test
        :param test_data: output data from a runner execution
        :type test_data: dict
        :returns: TestResults
        """
        stdout = test_data["stdout"]

        match = re.search(
            r"Summary:\n"
            r"passed\s*(?P<passed>\d+)\n"
            r"failed\s*(?P<failed>\d+)\n"
            r"broken\s*(?P<broken>\d+)\n"
            r"skipped\s*(?P<skipped>\d+)\n"
            r"warnings\s*(?P<warnings>\d+)\n",
            stdout
        )

        passed = 0
        failed = 0
        skipped = 0
        broken = 0
        skipped = 0
        warnings = 0
        retcode = test_data["returncode"]
        exec_time = test_data["exec_time"]

        if match:
            passed = int(match.group("passed"))
            failed = int(match.group("failed"))
            skipped = int(match.group("skipped"))
            broken = int(match.group("broken"))
            skipped = int(match.group("skipped"))
            warnings = int(match.group("warnings"))
        else:
            passed = stdout.count("TPASS")
            failed = stdout.count("TFAIL")
            skipped = stdout.count("TSKIP")
            broken = stdout.count("TBROK")
            warnings = stdout.count("TWARN")

            if passed == 0 and \
                    failed == 0 and \
                    skipped == 0 and \
                    broken == 0 and \
                    warnings == 0:
                # if no results are given, this is probably an
                # old test implementation that fails when return
                # code is != 0
                if retcode != 0:
                    failed = 1
                else:
                    passed = 1

        result = TestResults(
            test=test,
            failed=failed,
            passed=passed,
            broken=broken,
            skipped=skipped,
            warnings=warnings,
            exec_time=exec_time,
            retcode=retcode,
            stdout=stdout,
        )

        return result

    @property
    def is_running(self) -> bool:
        """
        Returns True if dispatcher is running tests. False otherwise.
        """
        raise NotImplementedError()

    def stop(self, timeout: int = 30) -> None:
        """
        Stop the current execution.
        :param timeout: timeout before stopping dispatcher
        :type timeout: int
        """
        raise NotImplementedError()

    def exec_suites(self, suites: list) -> list:
        """
        Execute a list of testing suites.
        :param suites: list of Suite objects
        :type suites: list(str)
        :returns: list(SuiteResults)
        """
        raise NotImplementedError()
