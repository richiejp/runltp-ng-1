"""
.. module:: serial
    :platform: Linux
    :synopsis: module containing serial dispatcher implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import time
from ltp import LTPException
from ltp.channel import Channel
from ltp.metadata import Suite
from ltp.metadata import Test
from ltp.metadata import RuntestMetadata
from ltp.results import SuiteResults
from ltp.results import TestResults
from .base import Dispatcher
from .base import DispatcherError


class SerialDispatcher(Dispatcher):
    """
    A dispatcher that serially runs jobs.
    """

    def __init__(self, **kwargs) -> None:
        """
        :param ltpdir: LTP install directory
        :type ltpdir: str
        :param tmpdir: session temporary directory
        :type tmpdir: str
        :param sut: SUT object
        :type sut: SUT
        :param events: session events object
        :type events: Events
        """
        self._ltpdir = kwargs.get("ltpdir", None)
        self._tmpdir = kwargs.get("tmpdir", None)
        self._sut = kwargs.get("sut", None)
        self._events = kwargs.get("events", None)
        self._is_running = False
        self._stop = False
        self._metadata = RuntestMetadata()

        if not self._ltpdir:
            raise ValueError("LTP directory doesn't exist")

        if not self._tmpdir or not os.path.isdir(self._tmpdir):
            raise ValueError("Temporary directory doesn't exist")

        if not self._sut:
            raise ValueError("SUT factory is empty")

        if not self._events:
            raise ValueError("No events are given")

    def _read_available_suites(self, channel: Channel) -> list:
        """
        Read the available testing suites by looking at runtest folder using
        ls command.
        """
        runtest_dir = os.path.join(self._ltpdir, "runtest")

        ret = channel.run_cmd(f"ls -1 {runtest_dir}", 2)

        retcode = ret["returncode"]
        if retcode != 0:
            raise DispatcherError("Can't read runtest folder")

        stdout = ret["stdout"]
        suites = [name.rstrip() for name in stdout.split("\n")]

        return suites

    @staticmethod
    def _read_sut_info(channel: Channel, cmd) -> str:
        """
        Read SUT information using command channel.
        """
        ret = channel.run_cmd(cmd, timeout=10)
        if ret["returncode"] != 0:
            raise DispatcherError(f"Can't read information from SUT: {cmd}")

        stdout = ret["stdout"].rstrip()

        return stdout

    @property
    def is_running(self) -> bool:
        return self._is_running

    def stop(self, timeout: int = 30) -> None:
        self._stop = True

        if self.is_running:
            secs = max(timeout, 0)
            start_t = time.time()

            while not self.is_running:
                time.sleep(0.05)
                if time.time() - start_t >= secs:
                    raise DispatcherError("Dispatcher timed out during stop")

    def _run_test(self, test: Test, env: dict) -> TestResults:
        """
        Run a single test and return the test results.
        """
        self._events.test_started(test)

        args = " ".join(test.arguments)
        cmd = f"{test.command} {args}"

        # wrapper around stdout callback
        def _mystdout_line(line):
            self._events.test_stdout_line(test, line)

        # TODO: set specific timeout for each test?
        test_data = self._sut.channel.run_cmd(
            cmd,
            timeout=3600,
            cwd=self._ltpdir,
            env=env,
            stdout_callback=_mystdout_line)

        results = self._get_test_results(test, test_data)

        self._events.test_completed(results)

        return results

    def _run_suite(self, suite: Suite) -> SuiteResults:
        """
        Run a single testing suite and return suite results.
        """
        env = {}
        env["LTPROOT"] = self._ltpdir
        env["LTP_COLORIZE_OUTPUT"] = os.environ.get("LTP_COLORIZE_OUTPUT", "n")

        # PATH must be set in order to run bash scripts
        testcases = os.path.join(self._ltpdir, "testcases", "bin")
        env["PATH"] = "/sbin:/usr/sbin:/usr/local/sbin:" + \
            f"/root/bin:/usr/local/bin:/usr/bin:/bin:{testcases}"

        suite_results = None

        try:
            self._events.suite_started(suite)

            # execute tests
            tests_results = []

            for test in suite.tests:
                if self._stop:
                    return None

                results = self._run_test(test, env)
                if not results:
                    break

                tests_results.append(results)

            # create suite results
            distro_str = self._read_sut_info(
                self._sut.channel,
                ". /etc/os-release; echo \"$ID\"")
            distro_ver_str = self._read_sut_info(
                self._sut.channel,
                ". /etc/os-release; echo \"$VERSION_ID\"")
            kernel_str = self._read_sut_info(
                self._sut.channel,
                "uname -s -r -v")
            arch_str = self._read_sut_info(
                self._sut.channel,
                "uname -m")

            suite_results = SuiteResults(
                suite=suite,
                tests=tests_results,
                distro=distro_str,
                distro_ver=distro_ver_str,
                kernel=kernel_str,
                arch=arch_str)
        finally:
            # read kernel messages for the current SUT instance
            dmesg_stdout = self._sut.channel.run_cmd("dmesg", timeout=10)
            command = os.path.join(self._tmpdir, f"dmesg_{suite.name}.log")
            with open(command, "w", encoding="utf-8") as fdmesg:
                fdmesg.write(dmesg_stdout["stdout"])

            if suite_results:
                self._events.suite_completed(suite_results)

        return suite_results

    def exec_suites(self, suites: list) -> list:
        if not suites:
            raise ValueError("suites list is empty")

        # create temporary directory where saving suites files
        tmp_suites = os.path.join(self._tmpdir, "suites")
        if not os.path.isdir(tmp_suites):
            os.mkdir(tmp_suites)

        self._is_running = True
        results = []

        try:
            avail_suites = self._read_available_suites(self._sut.channel)
            if set(avail_suites).issubset(set(suites)):
                raise DispatcherError(
                    "'Some suites are not available. Available suites are: "
                    f"{' '.join(avail_suites)}")

            for suite_name in suites:
                if self._stop:
                    break

                # download testing suite inside temporary directory
                target = os.path.join(self._ltpdir, "runtest", suite_name)
                local = os.path.join(tmp_suites, suite_name)

                self._events.suite_download_started(
                    suite_name,
                    target,
                    local)

                self._sut.channel.fetch_file(target, local)

                self._events.suite_download_completed(
                    suite_name,
                    target,
                    local)

                suite = self._metadata.read_suite(local)

                result = self._run_suite(suite)
                if not result:
                    break

                results.append(result)
        except LTPException as err:
            self._events.session_error(str(err))
            raise err
        finally:
            self._is_running = False
            self._stop = False

        return results
