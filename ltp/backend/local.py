"""
.. module:: local
    :platform: Linux
    :synopsis: module containing Backend definition for local testing execution

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
from ltp.downloader import LocalDownloader
from ltp.runner import ShellRunner
from .base import Backend


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

        self._downloader = LocalDownloader()
        self._runner = ShellRunner(ltp_dir, env)

    def communicate(self) -> set:
        return self._downloader, self._runner

    def stop(self) -> None:
        pass

    def force_stop(self) -> None:
        pass
