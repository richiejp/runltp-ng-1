"""
.. module:: shell
    :platform: Linux
    :synopsis: shell Runner implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import subprocess
import logging
from threading import Timer
from .base import Runner
from .base import RunnerError


class ShellRunner(Runner):
    """
    Shell Runner implementation class.
    """

    def __init__(self, cwd: str = None, env: dict = None) -> None:
        """
        :param cwd: current working directory
        :type cwd: str
        :param env: environment variables
        :type env: dict
        """
        self._logger = logging.getLogger("ltp.runner.shell")
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
            raise RunnerError("No process running")

        self._logger.info("Terminating process")
        self._process.terminate()
        self._logger.info("Process terminated")

    def force_stop(self) -> None:
        if not self._process:
            raise RunnerError("No process running")

        self._logger.info("Killing process")
        self._process.kill()
        self._logger.info("Process killed")

    def _run_cmd_impl(self, command: str, timeout: int) -> dict:
        if self._process:
            self._logger.debug(
                "Process with pid=%d is already running",
                self._process.pid)

            raise RunnerError("A command is already running")

        if not command:
            raise ValueError("command is empty")

        timeout = max(timeout, 0)

        self._logger.info(
            "Executing command (timeout=%d): %s", timeout, command)

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
        timer = None

        try:
            stdout = ""
            t_secs = max(timeout, 0)

            if t_secs > 0:
                def _threaded():
                    self._logger.info("Command timed out")
                    self._process.kill()

                timer = Timer(t_secs, _threaded)
                timer.start()

            while True:
                line = self._process.stdout.readline()
                if not line and self._process.poll() is not None:
                    break

                self._logger.info(line.rstrip())
                stdout += line

            ret = {
                "command": command,
                "stdout": stdout,
                "returncode": self._process.returncode,
                "timeout": t_secs,
            }
            self._logger.debug("return data=%s", ret)
        except subprocess.TimeoutExpired as err:
            self._process.kill()
            raise RunnerError from err
        finally:
            self._process = None
            if timer:
                timer.cancel()

        self._logger.info("Command executed")

        return ret
