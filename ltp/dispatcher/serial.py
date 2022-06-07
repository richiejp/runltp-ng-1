"""
.. module:: serial
    :platform: Linux
    :synopsis: module containing serial dispatcher implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import time
import logging
from ltp.sut import SUTTimeoutError
from ltp.metadata import Suite
from ltp.metadata import Test
from ltp.metadata import RuntestMetadata
from ltp.results import SuiteResults
from ltp.results import TestResults
from .base import Dispatcher
from .base import DispatcherError
from .base import SuiteTimeoutError


class SerialDispatcher(Dispatcher):
    """
    A dispatcher that serially runs jobs.
    """

    TAINED_MSG = [
        "proprietary module was loaded",
        "module was force loaded",
        "kernel running on an out of specification system",
        "module was force unloaded",
        "processor reported a Machine Check Exception (MCE)",
        "bad page referenced or some unexpected page flags",
        "taint requested by userspace application",
        "kernel died recently, i.e. there was an OOPS or BUG",
        "ACPI table overridden by user",
        "kernel issued warning",
        "staging driver was loaded",
        "workaround for bug in platform firmware applied",
        "externally-built (“out-of-tree”) module was loaded",
        "unsigned module was loaded",
        "soft lockup occurred",
        "kernel has been live patched",
        "auxiliary taint, defined for and used by distros",
        "kernel was built with the struct randomization plugin"
    ]

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
        :param suite_timeout: timeout for single suite. Default: 3600
        :type suite_timeout: int
        :param test_timeout: timeout for single suite. Default: 3600
        :type test_timeout: int
        """
        self._logger = logging.getLogger("ltp.dispatcher.serial")
        self._ltpdir = kwargs.get("ltpdir", None)
        self._tmpdir = kwargs.get("tmpdir", None)
        self._sut = kwargs.get("sut", None)
        self._events = kwargs.get("events", None)
        self._suite_timeout = max(kwargs.get("suite_timeout", 3600), 0)
        self._test_timeout = max(kwargs.get("test_timeout", 3600), 0)
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

    def _read_available_suites(self) -> list:
        """
        Read the available testing suites by looking at runtest folder using
        ls command.
        """
        runtest_dir = os.path.join(self._ltpdir, "runtest")

        ret = self._sut.run_command(f"ls -1 {runtest_dir}", timeout=10)

        retcode = ret["returncode"]
        if retcode != 0:
            raise DispatcherError("Can't read runtest folder")

        stdout = ret["stdout"]
        suites = [name.rstrip() for name in stdout.split("\n")]

        return suites

    def _read_sut_info(self, cmd) -> str:
        """
        Read SUT information.
        """
        ret = self._sut.run_command(cmd, timeout=10)
        if ret["returncode"] != 0:
            raise DispatcherError(f"Can't read information from SUT: {cmd}")

        stdout = ret["stdout"].rstrip()

        return stdout

    @property
    def is_running(self) -> bool:
        return self._is_running

    def stop(self, timeout: int = 30) -> None:
        self._logger.info("Stopping dispatcher")

        self._stop = True

        if self.is_running:
            secs = max(timeout, 0)
            start_t = time.time()

            while not self.is_running:
                time.sleep(0.05)
                if time.time() - start_t >= secs:
                    raise DispatcherError("Dispatcher timed out during stop")

        self._logger.info("Dispatcher topped")

    def _check_tained(self) -> set:
        """
        Return tained messages if kernel is tained.
        """
        self._logger.info("Checking for tained kernel")

        ret = self._sut.run_command(
            "cat /proc/sys/kernel/tainted",
            timeout=10)

        if ret["returncode"] != 0:
            raise DispatcherError("Error reading /proc/sys/kernel/tainted")

        tained_num = len(self.TAINED_MSG)

        code = int(ret["stdout"].rstrip())
        bits = format(code, f"0{tained_num}b")[::-1]

        messages = []
        for i in range(0, tained_num):
            if bits[i] == "1":
                msg = self.TAINED_MSG[i]
                messages.append(msg)

        self._logger.info("Tained kernel: %s", messages)

        return code, messages

    def _reboot_sut(self, force: bool = False) -> None:
        """
        This method reboot SUT if needed, for example, after a Kernel panic.
        """
        self._logger.info("Rebooting SUT")
        self._events.sut_restart(self._sut.name)

        def _mystdout_line(line: str) -> None:
            self._events.sut_stdout_line(self._sut.name, line)

        if force:
            self._sut.force_stop()
        else:
            self._sut.stop()

        self._sut.communicate(stdout_callback=_mystdout_line)

        self._logger.info("SUT rebooted")

    def _run_test(self, test: Test, env: dict) -> TestResults:
        """
        Run a single test and return the test results.
        """
        self._logger.info("Running test %s", test.name)
        self._logger.debug(test)

        self._events.test_started(test)

        args = " ".join(test.arguments)
        cmd = f"{test.command} {args}"

        test_data = None

        # we save stdout just in case we get kernel panic and we
        # can't get results data
        stdout = []
        timed_out = False
        tained_code_before = 0

        try:
            # check for tained kernel status
            tained_code_before, tained_msg_before = self._check_tained()
            if tained_msg_before:
                for msg in tained_msg_before:
                    self._events.kernel_tained(msg)

            # wrapper around stdout callback
            def _mystdout_line(line):
                self._events.test_stdout_line(test, line)
                stdout.append(line)

            test_data = self._sut.run_command(
                cmd,
                timeout=self._test_timeout,
                cwd=self._ltpdir,
                env=env,
                stdout_callback=_mystdout_line)
        except SUTTimeoutError:
            timed_out = True

            if any("Kernel panic" in msg for msg in stdout):
                self._events.kernel_panic()
                self._reboot_sut(force=True)
            else:
                try:
                    # check if SUT still replies to commands..
                    self._sut.run_command("test .", timeout=3)

                    # SUT is replying. Only test timed out
                    self._events.test_timed_out(test.name, self._test_timeout)
                except SUTTimeoutError:
                    # ..if not, we reboot the SUT
                    self._logger.info("SUT is not replying")

                    self._events.sut_not_responding()
                    self._reboot_sut(force=True)

            # emulate test reply
            test_data = {
                "name": test.name,
                "command": test.command,
                "stdout": "\n".join(stdout),
                "returncode": -1,
                "exec_time": self._test_timeout,
                "cwd": self._ltpdir,
                "env": env
            }

        results = self._get_test_results(
            test,
            test_data,
            timed_out=timed_out)

        # check again for tained kernel and if tained status has changed
        # just raise an exception and reboot the SUT
        tained_code_after, tained_msg_after = self._check_tained()
        if tained_code_before != tained_code_after:
            for msg in tained_msg_after:
                self._events.kernel_tained(msg)

        self._events.test_completed(results)

        self._logger.info("Test completed")
        self._logger.debug(results)

        if tained_code_before != tained_code_after:
            # reboot the system if it's not host
            if self._sut.name != "host":
                self._reboot_sut()

        return results

    # pylint: disable=too-many-locals
    def _run_suite(self, suite: Suite) -> SuiteResults:
        """
        Run a single testing suite and return suite results.
        """
        self._logger.info("Running suite %s", suite.name)
        self._logger.debug(suite)

        env = {}
        env["LTPROOT"] = self._ltpdir
        env["LTP_COLORIZE_OUTPUT"] = os.environ.get("LTP_COLORIZE_OUTPUT", "n")

        # PATH must be set in order to run bash scripts
        testcases = os.path.join(self._ltpdir, "testcases", "bin")
        env["PATH"] = "/sbin:/usr/sbin:/usr/local/sbin:" + \
            f"/root/bin:/usr/local/bin:/usr/bin:/bin:{testcases}"

        self._events.suite_started(suite)

        # execute tests
        tests_results = []

        start_t = time.time()

        for test in suite.tests:
            if self._stop:
                return None

            results = self._run_test(test, env)
            if not results:
                break

            tests_results.append(results)

            if time.time() - start_t >= self._suite_timeout:
                raise SuiteTimeoutError(
                    f"{suite.name} suite timed out "
                    f"(timeout={self._suite_timeout})")

        self._logger.info("Reading SUT information")

        # create suite results
        distro_str = self._read_sut_info(
            ". /etc/os-release; echo \"$ID\"")
        distro_ver_str = self._read_sut_info(
            ". /etc/os-release; echo \"$VERSION_ID\"")
        kernel_str = self._read_sut_info(
            "uname -s -r -v")
        arch_str = self._read_sut_info(
            "uname -m")

        suite_results = SuiteResults(
            suite=suite,
            tests=tests_results,
            distro=distro_str,
            distro_ver=distro_ver_str,
            kernel=kernel_str,
            arch=arch_str)

        self._logger.info("Storing dmesg information")

        # read kernel messages for the current SUT instance
        dmesg_stdout = self._sut.run_command("dmesg", timeout=60)
        command = os.path.join(self._tmpdir, f"dmesg_{suite.name}.log")
        with open(command, "w", encoding="utf-8") as fdmesg:
            fdmesg.write(dmesg_stdout["stdout"])

        if suite_results:
            self._events.suite_completed(suite_results)

        self._logger.debug(suite_results)
        self._logger.info("Suite completed")

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
            avail_suites = self._read_available_suites()
            if len(avail_suites) != len(suites) and \
                    set(avail_suites).issubset(set(suites)):
                raise DispatcherError(
                    "Some suites are not available. Available suites are: "
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

                self._sut.fetch_file(target, local)

                self._events.suite_download_completed(
                    suite_name,
                    target,
                    local)

                suite = self._metadata.read_suite(local)

                result = self._run_suite(suite)
                if not result:
                    break

                results.append(result)
        finally:
            self._is_running = False
            self._stop = False

        return results
