"""
.. module:: events
    :platform: Linux
    :synopsis: module containing session events

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ltp.metadata import Test
from ltp.metadata import Suite
from ltp.results import TestResults
from ltp.results import SuiteResults

# pylint: disable=too-many-public-methods


class Events:
    """
    Events class can be used to customize user interface using different
    libraries.
    """

    def session_started(self, tmpdir: str) -> None:
        """
        Raised when a new session has started.
        :param tmpdir: temporary directory
        :type tmpdir: str
        """
        pass

    def session_completed(self, results: list) -> None:
        """
        Raised when a session has completed.
        :param suites: list of testing suites results
        :type suites: list(SuiteResults)
        """
        pass

    def session_stopped(self) -> None:
        """
        Raised when a session has been stopped by the user.
        """
        pass

    def session_error(self, error: str) -> None:
        """
        Raised when session ends because of an internal error.
        :param error: error message
        :type error: str
        """
        pass

    def sut_start(self, sut: str) -> None:
        """
        Raised when SUT is starting.
        :param SUT: name of the SUT
        :type sut: str
        """
        pass

    def sut_restart(self, sut: str) -> None:
        """
        Raised when SUT is restarting.
        :param SUT: name of the SUT
        :type sut: str
        """
        pass

    def sut_stop(self, sut: str) -> None:
        """
        Raised when SUT has stopped.
        :param SUT: name of the SUT
        :type sut: str
        """
        pass

    def sut_stdout_line(self, sut: str, line: str) -> None:
        """
        Raised when SUT is starting and send information to stdout.
        Called when a line come out from stdout.
        :param SUT: name of the SUT
        :type sut: str
        :param line: line arrived to stdout
        :type line: str
        """
        pass

    def suite_download_started(
            self,
            name: str,
            target: str,
            local: str) -> None:
        """
        Raised when testing suite file is downloaded in local host.
        :param name: testing suite name
        :type name: str
        :param target: testing suite target path
        :type target: str
        :param local: testing suite local path
        :type local: str
        """
        pass

    def suite_download_completed(
            self,
            name: str,
            target: str,
            local: str) -> None:
        """
        Raised when testing suite file has been downloaded in local host.
        :param name: testing suite name
        :type name: str
        :param target: testing suite target path
        :type target: str
        :param local: testing suite local path
        :type local: str
        """
        pass

    def suite_started(self, suite: Suite) -> None:
        """
        Raised when a new suite has started.
        :param suite: running suite
        :type suite: Suite
        """
        pass

    def suite_completed(self, results: SuiteResults) -> None:
        """
        Raised when a suite has been completed.
        :param results: completed testing suite results
        :type results: SuiteResults
        """
        pass

    def test_started(self, test: Test) -> None:
        """
        Raised when a new test has started.
        :param test: running test
        :type test: Test
        """
        pass

    def test_stdout_line(self, test: Test, line: str) -> None:
        """
        Raised when a test sends a new line in the stdout.
        :param test: running test
        :type test: Test
        :param line: line in the stdout
        :type line: str
        """
        pass

    def test_completed(self, results: TestResults) -> None:
        """
        Raised when a test has completed.
        :param results: completed test results
        :type results: TestResults
        """
        pass

    def run_cmd_start(self, cmd: str) -> None:
        """
        Raised when a new command is going to be run.
        :param cmd: command to run
        :type cmd: str
        """
        pass

    def run_cmd_stdout(self, line: str) -> None:
        """
        Raised when a new command has run.
        :param line: stdout line
        :type line: str
        """
        pass

    def run_cmd_stop(self, cmd: str, returncode: int) -> None:
        """
        Raised when a new command has stopped.
        :param cmd: command to run
        :type cmd: str
        :param returncode: command return code
        :type returncode: int
        """
        pass

    def show_tests_list(self, suites: list) -> None:
        """
        Raised when user asked for suites list.
        :param pkgs: list of suites names
        :type pkgs: list(str)
        """
        pass

    def show_install_dependences(
            self,
            refresh_cmd: str,
            install_cmd: str,
            pkgs: list) -> None:
        """
        Raised when user asked for install dependences.
        :param refresh_cmd: command to refresh packages database
        :type refresh_cmd: str
        :param install_cmd: command to install packages
        :type install_cmd: str
        :param pkgs: list of packages to install
        :type pkgs: list(str)
        """
        pass

    def install_started(
            self,
            m32: bool,
            url: str,
            repo_dir: str,
            install_dir: str) -> None:
        """
        Raised when a new installation of LTP has started.
        :param m32: True for 32bit support
        :type m32: bool
        :param url: url where LTP repo is located
        :type url: str
        :param repo_dir: local repo directory
        :type repo_dir: str
        :param install_dir: LTP install directory
        :type install_dir: str
        """
        pass

    def install_completed(self) -> None:
        """
        Raised when a new installation of LTP has completed.
        """
        pass

    def install_error(self, error: str) -> None:
        """
        Raised when a new installation of LTP has been stopped.
        :param err: error message
        :type errr: str
        """
        pass

    def install_stopped(self) -> None:
        """
        Raised when a new installation of LTP has been stopped.
        """
        pass

    def install_requirements_started(self) -> None:
        """
        Raised when requirements are going to be installed.
        """
        pass

    def install_requirements_completed(self) -> None:
        """
        Raised when requirements have been installed.
        """
        pass

    def install_clone_repo_started(self, repo: str, repo_dir: str) -> None:
        """
        Raised when repository is being cloned.
        :param repo: repository to clone
        :type repo: str
        :param repo_dir: local repo directory
        :type repo_dir: str
        """
        pass

    def install_clone_repo_completed(self, repo: str, repo_dir: str) -> None:
        """
        Raised when repository has been cloned.
        :param repo: repository to clone
        :type repo: str
        :param repo_dir: local repo directory
        :type repo_dir: str
        """
        pass

    def install_compile_started(self, path: str) -> None:
        """
        Raised when LTP is being compiled.
        :param path: LTP source code path
        :type path: str
        """
        pass

    def install_compile_completed(self, install_dir: str) -> None:
        """
        Raised when LTP has been compiled.
        :param install_dir: LTP install directory
        :type install_dir: str
        """
        pass

    def install_stdout_line(self, line: str) -> None:
        """
        Raised when a new line arrived in the stdout.
        :param line: new line in the stdout
        :type line: str
        """
        pass
