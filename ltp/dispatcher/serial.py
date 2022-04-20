"""
.. module:: serial
    :platform: Linux
    :synopsis: module containing serial dispatcher implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
from ltp.runner import Runner
from ltp.backend import BackendFactory
from ltp.metadata import RuntestMetadata
from ltp.results import SuiteResults
from .base import Dispatcher
from .base import DispatcherError


class SerialDispatcher(Dispatcher):
    """
    A dispatcher that serially runs jobs.
    """

    def __init__(
            self,
            ltpdir: str,
            tmpdir: str,
            backend_factory: BackendFactory) -> None:
        """
        :param ltpdir: LTP install directory
        :type ltpdir: str
        :param tmpdir: session temporary directory
        :type tmpdir: str
        :param backend_factory: backend factory object
        :type backend_factory: BackendFactory
        """
        self._ltpdir = ltpdir
        self._tmpdir = tmpdir
        self._is_running = False
        self._stop = False
        self._backend_factory = backend_factory
        self._metadata = RuntestMetadata()

        if not self._tmpdir or not os.path.isdir(self._tmpdir):
            raise ValueError("Temporary directory doesn't exist")

        if not self._backend_factory:
            raise ValueError("Backend factory is empty")

    def _read_available_suites(self, runner: Runner) -> list:
        """
        Read the available testing suites by looking at runtest folder using
        ls command.
        """
        runtest_dir = os.path.join(self._ltpdir, "runtest")

        ret = runner.run_cmd(f"ls -1 {runtest_dir}", 2)

        retcode = ret["returncode"]
        if retcode != 0:
            raise DispatcherError("Can't read runtest folder")

        stdout = ret["stdout"]
        suites = [name.rstrip() for name in stdout.split("\n")]

        return suites

    @staticmethod
    def _read_sut_info(runner: Runner, cmd) -> str:
        """
        Read SUT information using command runner.
        """
        ret = runner.run_cmd(cmd, 10)
        if ret["returncode"] != 0:
            raise DispatcherError(f"Can't read information from SUT: {cmd}")

        stdout = ret["stdout"].rstrip()

        return stdout

    @property
    def is_running(self) -> bool:
        return self._is_running

    def stop(self) -> None:
        self._stop = True

    # pylint: disable=too-many-locals
    def exec_suites(self, suites: list) -> list:
        if not suites:
            raise ValueError("suites list is empty")

        # create temporary directory where saving suites files
        tmp_suites = os.path.join(self._tmpdir, "suites")
        if not os.path.isdir(tmp_suites):
            os.mkdir(tmp_suites)

        self._is_running = True
        avail_suites = []
        results = []

        env = {}
        env["LTPROOT"] = self._ltpdir
        env["TMPDIR"] = self._tmpdir
        env["LTP_COLORIZE_OUTPUT"] = os.environ.get("LTP_COLORIZE_OUTPUT", "y")

        # PATH must be set in order to run bash scripts
        testcases = os.path.join(self._ltpdir, "testcases", "bin")
        env["PATH"] = f'$PATH:{testcases}'

        try:
            for suite_name in suites:
                if self._stop:
                    break

                backend = self._backend_factory.create()

                try:
                    backend.communicate()

                    if not avail_suites:
                        avail_suites = self._read_available_suites(
                            backend.runner)

                    if suite_name not in avail_suites:
                        raise DispatcherError(
                            f"'{suite_name}' is not available. "
                            "Available suites are: "
                            f"{' '.join(avail_suites)}"
                        )

                    # download testing suite inside temporary directory
                    # TODO: handle different metadata
                    target = os.path.join(self._ltpdir, "runtest", suite_name)
                    local = os.path.join(tmp_suites, suite_name)
                    backend.downloader.fetch_file(target, local)

                    # convert testing suites files
                    suite = self._metadata.read_suite(local)

                    # execute tests
                    tests_results = []
                    backend.runner.start()

                    for test in suite.tests:
                        if self._stop:
                            backend.runner.stop()
                            break

                        args = " ".join(test.arguments)
                        cmd = f"{test.command} {args}"

                        # TODO: set specific timeout for each test?
                        test_data = backend.runner.run_cmd(
                            cmd,
                            timeout=3600,
                            cwd=self._ltpdir,
                            env=env)

                        test_results = self._get_test_results(test, test_data)
                        tests_results.append(test_results)

                    # create suite results
                    distro_str = self._read_sut_info(
                        backend.runner,
                        ". /etc/os-release; echo \"$ID\"")
                    distro_ver_str = self._read_sut_info(
                        backend.runner,
                        ". /etc/os-release; echo \"$VERSION_ID\"")
                    kernel_str = self._read_sut_info(
                        backend.runner,
                        "uname -s -r -v")
                    arch_str = self._read_sut_info(
                        backend.runner,
                        "uname -m")

                    suite_results = SuiteResults(
                        suite=suite,
                        tests=tests_results,
                        distro=distro_str,
                        distro_ver=distro_ver_str,
                        kernel=kernel_str,
                        arch=arch_str)

                    results.append(suite_results)
                finally:
                    backend.stop()
        finally:
            self._is_running = False
            self._stop = False

        return results
