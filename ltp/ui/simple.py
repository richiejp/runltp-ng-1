"""
.. module:: simple
    :platform: Linux
    :synopsis: module containing simple user interface definition.

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import platform
import traceback
from ltp.metadata import Test
from ltp.metadata import Suite
from ltp.results import TestResults
from ltp.results import SuiteResults
from ltp.common.events import Events

# pylint: disable=too-many-public-methods


class SimpleConsoleEvents(Events):
    """
    Simple events implementation for the console based user interface.
    """

    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    RED = "\033[1;31m"
    CYAN = "\033[1;36m"

    def __init__(self, verbose: bool = False) -> None:
        self._verbose = verbose

    @staticmethod
    def _print(msg: str, color: str = None, end: str = "\n"):
        """
        Print a message.
        """
        if color:
            print(color + msg + '\033[0m', end=end)
        else:
            print(msg, end=end)

    def session_started(self, _: list, tmpdir: str) -> None:
        uname = platform.uname()
        message = "Host information\n\n"
        message += f"\tSystem: {uname.system}\n"
        message += f"\tNode: {uname.node}\n"
        message += f"\tKernel Release: {uname.release}\n"
        message += f"\tKernel Version: {uname.version}\n"
        message += f"\tMachine Architecture: {uname.machine}\n"
        message += f"\tProcessor: {uname.processor}\n"
        message += f"\n\tTemporary directory: {tmpdir}\n"

        self._print(message)

    def session_stopped(self) -> None:
        self._print("Session stopped")

    def session_error(self, error: str) -> None:
        message = f"Error: {error}"

        if self._verbose:
            trace = traceback.format_exc()
            if trace:
                message += f"\n\n{trace}"

        self._print(message)

    def sut_start(self, sut: str) -> None:
        self._print(f"Connecting to SUT: {sut}")

    def sut_stop(self, sut: str) -> None:
        self._print(f"Disconnecting from SUT: {sut}")

    def sut_stdout_line(self, _: str, line: str) -> None:
        if self._verbose:
            self._print(line)

    def suite_download_started(
            self,
            name: str,
            target: str,
            local: str) -> None:
        if self._verbose:
            self._print(
                f"Downloading suite: {target} -> {local}")
        else:
            self._print(f"Downloading suite: {name}")

    def suite_started(self, suite: Suite) -> None:
        self._print(f"Starting suite: {suite.name}")

    def suite_completed(self, results: SuiteResults) -> None:
        message = "\n"
        message += f"Suite Name: {results.suite.name}\n"
        message += f"Total Run: {len(results.suite.tests)}\n"
        message += f"Elapsed Time: {results.exec_time:.1f} seconds\n"
        message += f"Passed Tests: {results.passed}\n"
        message += f"Failed Tests: {results.failed}\n"
        message += f"Skipped Tests: {results.skipped}\n"
        message += f"Broken Tests: {results.broken}\n"
        message += f"Warnings: {results.warnings}\n"
        message += f"Kernel Version: {results.kernel}\n"
        message += f"Machine Architecture: {results.arch}\n"
        message += f"Distro: {results.distro}\n"
        message += f"Distro Version: {results.distro_ver}\n\n"

        self._print(message)

    def test_started(self, test: Test) -> None:
        msg = f"{test.name}: "
        if self._verbose:
            msg = f"running {test.name}\n"

        self._print(msg, end="")

    def test_completed(self, results: TestResults) -> None:
        if self._verbose:
            return

        msg = "pass"
        col = self.GREEN

        if results.failed > 0:
            msg = "fail"
            col = self.RED
        elif results.skipped > 0:
            msg = "skip"
            col = self.YELLOW
        elif results.broken > 0:
            msg = "broken"
            col = self.CYAN

        self._print(msg, color=col)

    def test_stdout_line(self, _: Test, line: str) -> None:
        if self._verbose:
            col = ""
            if "TPASS" in line:
                col = self.GREEN
            elif "TFAIL" in line:
                col = self.RED
            elif "TSKIP" in line:
                col = self.YELLOW
            elif "TCONF" in line:
                col = self.CYAN

            self._print(line, color=col)

    def show_install_dependences(
            self,
            refresh_cmd: str,
            install_cmd: str,
            pkgs: list) -> None:
        message = ""
        if refresh_cmd:
            message += refresh_cmd

        if install_cmd:
            message += " && "
            message += install_cmd
            message += " "

        message += " ".join(pkgs)

        self._print(f"{message}")

    def show_tests_list(self, suites: list) -> None:
        for suite in suites:
            self._print(f"{suite}")

    def install_started(
            self,
            m32: bool,
            url: str,
            repo_dir: str,
            install_dir: str) -> None:
        message = "\n"
        message += f"Repo URL: {url}\n"
        message += f"Repo Directory: {repo_dir}\n"
        message += f"Install Directory: {install_dir}\n"
        message += "32bit Support: "
        message += "Enabled\n" if m32 else "Disabled\n"

        self._print(message)

    def install_completed(self) -> None:
        self._print("Done!")

    def install_stopped(self) -> None:
        self._print("Install stopped")

    def install_error(self, error: str) -> None:
        message = f"Error: {error}"

        if self._verbose:
            trace = traceback.format_exc()
            if trace:
                message += f"\n\n{trace}"

        self._print(message)

    def install_requirements_started(self) -> None:
        self._print("Installing requirements")

    def install_requirements_completed(self) -> None:
        self._print("Requirements installed")

    def install_clone_repo_started(self, repo: str, _: str) -> None:
        self._print(f"Start cloning repository: {repo}")

    def install_clone_repo_completed(self, _: str, repo_dir: str) -> None:
        self._print(f"Repository cloned in {repo_dir}")

    def install_compile_started(self, path: str) -> None:
        self._print(f"Compiling LTP from folder: {path}")

    def install_compile_completed(self, install_dir: str) -> None:
        self._print(f"LTP installed: {install_dir}")

    def install_stdout_line(self, line: str) -> None:
        if self._verbose:
            self._print(line)
