"""
.. module:: local
    :platform: Linux
    :synopsis: module containing Backend definition for local testing execution

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
from ltp.runner import Runner
from ltp.runner import ShellRunner
from ltp.downloader import Downloader
from ltp.downloader import LocalDownloader
from .base import Backend
from .base import BackendError
from .base import BackendFactory


class LocalBackend(Backend):
    """
    Local backend implementation for host testing.
    """

    def __init__(self, ltp_dir: str, tmp_dir: str) -> None:
        """
        :param ltp_dir: LTP installation directory
        :type ltp_dir: str
        :param tmp_dir: session temporary directory
        :type tmp_dir: str
        """
        if not ltp_dir or not os.path.isdir(ltp_dir):
            raise ValueError("LTP directory doesn't exist")

        if not tmp_dir or not os.path.isdir(tmp_dir):
            raise ValueError("Temporary directory doesn't exist")

        tmp_tests = os.path.join(tmp_dir, "local")
        if not os.path.isdir(tmp_tests):
            os.mkdir(tmp_tests)

        env = {}
        env["LTPROOT"] = ltp_dir
        env["TMPDIR"] = tmp_tests
        env["LTP_COLORIZE_OUTPUT"] = os.environ.get("LTP_COLORIZE_OUTPUT", "y")

        # PATH must be set in order to run bash scripts
        testcases = os.path.join(ltp_dir, "testcases", "bin")
        env["PATH"] = f'{os.environ.get("PATH")}:{testcases}'

        self._ltp_dir = ltp_dir
        self._env = env
        self._downloader = None
        self._runner = None

    @property
    def downloader(self) -> Downloader:
        return self._downloader

    @property
    def runner(self) -> Runner:
        return self._runner

    def communicate(self) -> None:
        if self._downloader or self._runner:
            raise BackendError("Backend is already running")

        self._downloader = LocalDownloader()
        self._runner = ShellRunner(self._ltp_dir, self._env)

    def stop(self) -> None:
        self._runner.stop()
        self._downloader.stop()

    def force_stop(self) -> None:
        self._runner.force_stop()
        self._downloader.stop()


class LocalBackendFactory(BackendFactory):
    """
    LocalBackend factory class.
    """

    def __init__(self, ltp_dir: str, tmp_dir: str) -> None:
        """
        :param ltp_dir: LTP installation directory
        :type ltp_dir: str
        :param tmp_dir: session temporary directory
        :type tmp_dir: str
        """
        if not ltp_dir or not os.path.isdir(ltp_dir):
            raise ValueError("LTP directory doesn't exist")

        if not tmp_dir or not os.path.isdir(tmp_dir):
            raise ValueError("Temporary directory doesn't exist")

        self._ltp_dir = ltp_dir
        self._tmp_dir = tmp_dir

    def create(self) -> Backend:
        backend = LocalBackend(self._ltp_dir, self._tmp_dir)
        return backend
