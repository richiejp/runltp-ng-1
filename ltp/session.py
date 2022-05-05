"""
.. module:: session
    :platform: Linux
    :synopsis: module that contains LTP session definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import pwd
import shutil
import pathlib
import tempfile
import logging
from ltp import LTPException
from ltp.channel.base import ChannelError
from ltp.install import INSTALLERS
from ltp.install import Installer
from ltp.install import InstallerError
from ltp.results import SuiteResults
from ltp.results import JSONExporter
from ltp.sut import SUT
from ltp.sut import LocalSUT
from ltp.sut import SSHSUT
from ltp.sut import QemuSUT
from ltp.ui import SimpleConsoleEvents
from ltp.dispatcher import SerialDispatcher


class SessionError(LTPException):
    """
    Raised when a new exception occurs during session.
    """


class TempRotator:
    """
    Temporary directory rotation class.
    """
    SYMLINK_NAME = "latest"

    def __init__(self, root: str, max_rotate: int = 5) -> None:
        """
        :param root: root temporary path
        :type root: str
        :param max_rotate: maximum number of rotations
        :type max_rotate: int
        """
        if not os.path.isdir(root):
            raise ValueError("root is empty")

        name = pwd.getpwuid(os.getuid()).pw_name
        self._tmpbase = os.path.join(root, f"runltp-of-{name}")
        self._max_rotate = max(max_rotate, 0)

    def rotate(self) -> str:
        """
        Check for old folders and remove them, then create a new one and return
        its full path.
        """
        os.makedirs(self._tmpbase, exist_ok=True)

        # delete the first max_rotate items
        sorted_paths = sorted(
            pathlib.Path(self._tmpbase).iterdir(),
            key=os.path.getmtime)

        # don't consider latest symlink
        num_paths = len(sorted_paths) - 1

        if num_paths >= self._max_rotate:
            max_items = num_paths - self._max_rotate + 1
            paths = sorted_paths[:max_items]

            for path in paths:
                if path.name == self.SYMLINK_NAME:
                    continue

                shutil.rmtree(str(path.resolve()))

        # create a new folder
        folder = tempfile.mkdtemp(dir=self._tmpbase)

        # create symlink to the latest temporary directory
        latest = os.path.join(self._tmpbase, self.SYMLINK_NAME)
        if os.path.islink(latest):
            os.remove(latest)

        os.symlink(
            folder,
            os.path.join(self._tmpbase, self.SYMLINK_NAME),
            target_is_directory=True)

        return folder


class Session:
    """
    The main session handler.
    """

    LTP_REPO = 'http://github.com/linux-test-project/ltp.git'
    LTP_DIR = '/opt/ltp'

    def __init__(
            self,
            suite_timeout: int = 3600,
            exec_timeout: int = 3600,
            verbose: bool = False) -> None:
        """
        :param verbose: if True, more messages will come from the console.
        :type verbose: bool
        :param suite_timeout: timeout before stopping testing suite
        :type suite_timeout: int
        :param exec_timeout: timeout before stopping single execution
        :type exec_timeout: int
        """
        self._logger = logging.getLogger("ltp.session")
        self._events = SimpleConsoleEvents(verbose=verbose)
        self._installer = None
        self._suite_timeout = suite_timeout
        self._exec_timeout = exec_timeout

    @staticmethod
    def _setup_debug_log(tmpdir: str) -> None:
        """
        Save a log file with debugging information
        """
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        debug_file = os.path.join(tmpdir, "debug.log")
        handler = logging.FileHandler(debug_file, encoding="utf8")
        handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s:%(lineno)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    def _print_results(self, suite_results: SuiteResults) -> None:
        """
        Print suite results.
        """
        tests = len(suite_results.tests_results)

        self._logger.info("")
        self._logger.info("Suite name: %s", suite_results.suite.name)
        self._logger.info("Total Run: %d", tests)
        self._logger.info("Elapsed time: %.1f s", suite_results.exec_time)
        self._logger.info("Total Passed Tests: %d", suite_results.passed)
        self._logger.info("Total Failed Tests: %d", suite_results.failed)
        self._logger.info("Total Skipped Tests: %d", suite_results.skipped)
        self._logger.info("Total Broken Tests: %d", suite_results.broken)
        self._logger.info("Total Warnings: %d", suite_results.warnings)
        self._logger.info("Kernel Version: %s", suite_results.kernel)
        self._logger.info("Machine Architecture: %s", suite_results.arch)
        self._logger.info("Distro: %s", suite_results.distro)
        self._logger.info("Distro version: %s", suite_results.distro_ver)
        self._logger.info("")

    @staticmethod
    def _get_installer(sut: SUT) -> Installer:
        """
        Return the proper installer according with SUT distribution.
        """
        result = sut.channel.run_cmd(". /etc/os-release && echo $ID")
        if result["returncode"] != 0:
            raise InstallerError("Can't find os-release on target")

        distro_id = result["stdout"].rstrip()

        installer = None
        for item in INSTALLERS:
            if item.distro_id in distro_id:
                installer = item
                break

        if not installer:
            raise InstallerError(f"{distro_id} is not supported")

        def _run_cmd(
                cmd: str,
                cwd: str = None,
                raise_err: bool = True,
                stdout_callback: callable = None) -> None:
            try:
                ret = sut.channel.run_cmd(
                    cmd,
                    timeout=3600,
                    cwd=cwd,
                    stdout_callback=stdout_callback)

                if ret["returncode"] != 0:
                    stdout = ret["stdout"]
                    raise InstallerError(f"'{cmd}' execution error: {stdout}")
            except ChannelError as err:
                if raise_err:
                    raise err

        # pylint: disable=protected-access
        installer._run_cmd = _run_cmd

        return installer

    # pylint: disable=too-many-arguments
    def _install_ltp(
            self,
            sut: SUT,
            tmpdir,
            repo: str,
            commit: str,
            branch: str = "master",
            m32: bool = False,
            install_dir: str = "/opt/ltp") -> None:
        """
        Install LTP inside SUT.
        """
        self._installer = self._get_installer(sut)

        try:
            repodir = os.path.join(tmpdir, "ltp-repo")
            self._events.install_requirements_started()

            self._installer.install_requirements(
                m32,
                self._events.install_stdout_line)

            self._events.install_requirements_completed()
            self._events.install_clone_repo_started(repo, repodir)

            self._installer.clone_repo(
                repo,
                repodir,
                branch=branch,
                commit=commit,
                stdout_callback=self._events.install_stdout_line)

            self._events.install_clone_repo_completed(repo, repodir)
            self._events.install_compile_started(repodir)

            self._installer.install_from_src(
                repodir,
                install_dir,
                self._events.install_stdout_line)

            self._events.install_compile_completed(install_dir)
        except InstallerError as err:
            self._installer.stop()

            raise SessionError(err)

    def _start_sut(self, ltpdir: str, tmpdir: str, sut_config: dict) -> None:
        """
        Start a new SUT and return it initialized.
        """
        sut_name = sut_config.get("name", None)
        if sut_name not in ["qemu", "ssh", "host"]:
            raise ValueError(f"{sut_name} is not supported")

        config = {}
        config['ltpdir'] = ltpdir
        config['tmpdir'] = tmpdir
        config.update(sut_config)

        sut = None
        if sut_name == 'qemu':
            sut = QemuSUT(**config)
        elif sut_name == 'ssh':
            sut = SSHSUT(**config)
        else:
            sut = LocalSUT()

        self._events.sut_start(sut.name)

        # wrapper around stdout callback
        # pylint: disable=cell-var-from-loop
        def _mystdout_line(line):
            self._events.sut_stdout_line(sut.name, line)

        sut.communicate(stdout_callback=_mystdout_line)

        return sut

    def _stop_sut(self, sut: SUT, timeout: int = 30) -> None:
        """
        Stop a specific SUT.
        """
        if not sut:
            return

        self._events.sut_stop(sut.name)

        if sut.channel:
            sut.stop(timeout=timeout)
        else:
            sut.force_stop(timeout=timeout)

    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    def run_single(
            self,
            sut_config: dict,
            git_config: dict,
            report_path: str,
            suites: list,
            command: str) -> None:
        """
        Run some testing suites with a specific SUT configurations.
        :param sut_config: system under test configuration.
        :type sut_config: dict
        :param git_config: Git repo configuration. If None, LTP won't
            be installed.
        :type git_config: dict
        :param suites: suites to execute
        :type suites: list
        :param command: command to execute
        :type command: str
        """
        if not sut_config:
            raise ValueError("sut configuration can't be empty")

        if report_path and os.path.isfile(report_path):
            raise ValueError("report file already exists")

        ltpdir = os.environ.get("LTPROOT", self.LTP_DIR)
        tmpbase = os.environ.get("TMPDIR", tempfile.gettempdir())
        tmpdir = TempRotator(tmpbase).rotate()

        self._logger.info("Running session using temporary folder: %s", tmpdir)

        self._setup_debug_log(tmpdir)
        self._events.session_started(tmpdir)

        sut = None
        dispatcher = None

        try:
            sut = self._start_sut(ltpdir, tmpdir, sut_config)

            self._logger.info("Created SUT: %s", sut.name)

            if git_config:
                self._install_ltp(
                    sut,
                    tmpdir,
                    git_config.get("repo", self.LTP_REPO),
                    git_config.get("commit", None),
                    branch=git_config.get("branch", "master"),
                    m32=git_config.get("m32", "0") == "1",
                    install_dir=git_config.get("install_dir", ltpdir))

            if command:
                self._events.run_cmd_start(command)

                def _mystdout_line(line):
                    self._events.run_cmd_stdout(line)

                ret = sut.channel.run_cmd(
                    command,
                    timeout=self._exec_timeout,
                    stdout_callback=_mystdout_line)

                self._events.run_cmd_stop(command, ret["returncode"])

            if suites:
                dispatcher = SerialDispatcher(
                    ltpdir=ltpdir,
                    tmpdir=tmpdir,
                    sut=sut,
                    events=self._events,
                    suite_timeout=self._suite_timeout,
                    test_timeout=self._exec_timeout)

                self._logger.info("Created dispatcher")

                results = dispatcher.exec_suites(suites)
                dispatcher.stop()

                if results:
                    for result in results:
                        self._print_results(result)

                    if report_path:
                        exporter = JSONExporter()
                        exporter.save_file(results, report_path)

                self._events.session_completed(results)

            self._stop_sut(sut)

            self._logger.info("Session completed")
        except LTPException as err:
            if self._installer:
                self._installer.stop()

            self._stop_sut(sut)

            if dispatcher:
                dispatcher.stop()

            self._logger.error("Error: %s", str(err))
            self._events.session_error(str(err))
        except KeyboardInterrupt:
            self._logger.info("Keyboard interrupt")

            if self._installer:
                self._installer.stop()

            self._stop_sut(sut)

            if dispatcher:
                dispatcher.stop()

            self._events.session_stopped()
