"""
.. module:: shell
    :platform: Linux
    :synopsis: shell backend implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import subprocess
import logging
from .base import Backend
from .base import BackendError


class ShellBackend(Backend):
    """
    Shell backend implementation class.
    """

    def __init__(self, cwd: str = None, env: dict = None) -> None:
        """
        :param cwd: current working directory
        :type cwd: str
        :param env: environment variables
        :type env: dict
        """
        self._logger = logging.getLogger("ltp.shell")
        self._process = None
        self._cwd = cwd
        self._env = env

    @property
    def name(self) -> str:
        return "shell"

    def start(self) -> None:
        pass

    def stop(self, _: int = 0) -> None:
        if not self._process:
            raise BackendError("No process running")

        self._process.terminate()

    def force_stop(self) -> None:
        if not self._process:
            raise BackendError("No process running")

        self._process.kill()

    def _run_cmd_impl(self, command: str, timeout: int) -> dict:
        if self._process:
            self._logger.debug(
                "Process with pid=%d is already running", self._process.pid)
            raise BackendError("A command is already running")

        if not command:
            raise ValueError("command is empty")

        timeout = max(timeout, 0)

        self._logger.info("Executing '%s' (timeout=%d)", command, timeout)

        # keep usage of preexec_fn trivial
        # see warnings in https://docs.python.org/3/library/subprocess.html
        # pylint: disable=subprocess-popen-preexec-fn
        # pylint: disable=consider-using-with
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self._cwd,
            env=self._env,
            shell=True,
            universal_newlines=True,
            preexec_fn=os.setsid)

        ret = None
        try:
            stdout = self._process.communicate(timeout=timeout)[0]
            self._logger.debug("stdout=%s", stdout)

            ret = {
                "command": command,
                "stdout": stdout,
                "returncode": self._process.returncode,
                "timeout": timeout,
            }
            self._logger.debug("return data=%s", ret)
        except subprocess.TimeoutExpired as err:
            self._process.kill()
            raise BackendError from err
        finally:
            self._process = None

        return ret
