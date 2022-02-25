"""
.. module:: shell
    :platform: Linux
    :synopsis: shell backend implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import subprocess
import logging
from .backend import Backend
from .backend import BackendError


class ShellBackend(Backend):
    """
    Shell backend implementation class.
    """

    def __init__(self, cwd: str = None, env: dict = None) -> None:
        self._logger = logging.getLogger("ltp.shell")
        self._process = None
        self._cwd = cwd
        self._env = env

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
            pid = self._process.pid
            self._logger.debug(f"Process with pid={pid} is already running")
            raise BackendError("A command is already running")

        if not command:
            raise ValueError("command is empty")

        if timeout < 0:
            timeout = 0

        self._logger.info("Executing '%s' (timeout=%d)", command, timeout)

        # keep usage of preexec_fn trivial
        # see warnings in https://docs.python.org/3/library/subprocess.html
        # pylint: disable=subprocess-popen-preexec-fn
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
            self._logger.debug(f"stdout={stdout}")

            ret = {
                "command": command,
                "stdout": stdout,
                "returncode": self._process.returncode,
                "timeout": timeout,
            }
            self._logger.debug(f"return data={ret}")
        except subprocess.TimeoutExpired:
            self._process.kill()
            raise BackendError(f"'{command}' command timed out")
        finally:
            self._process = None

        return ret
