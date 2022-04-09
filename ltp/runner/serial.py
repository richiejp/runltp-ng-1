"""
.. module:: serial
    :platform: Linux
    :synopsis: module containing serial Runner definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import re
import time
import string
import secrets
import logging
from typing import IO
from .base import Runner
from .base import RunnerError


class SerialRunner(Runner):
    """
    This is not a standard serial I/O protocol communication class, but rather
    a helper class for sessions where a serial hw channel is exposed via file
    descriptor. This is really common in a qemu session, where console is
    exposed in the host system via file descriptor.
    """

    def __init__(self,
                 stdout: IO,
                 stdin: IO,
                 ignore_echo: bool = True) -> None:
        """
        :param stdin: standard input file handler
        :type stdin: IO
        :param stdout: standard output file handler
        :type stdout: IO
        :param ignore_echo: if True, echoed commands will be ignored
        :type ignore_echo: bool
        """
        self._logger = logging.getLogger("ltp.runner.serial")
        self._stdin = stdin
        self._stdout = stdout
        self._ignore_echo = ignore_echo
        self._stop = False

        if not self._stdin:
            raise ValueError("stdin is empty")

        if not self._stdout:
            raise ValueError("stdout is empty")

    @property
    def name(self) -> str:
        return "serial"

    # pylint: disable=consider-using-with
    def start(self) -> None:
        pass

    def stop(self, _: int = 0) -> None:
        self._logger.info("Stopping command")
        self._stop = True

    def force_stop(self) -> None:
        self.stop()

    @staticmethod
    def _generate_string(length: int = 10) -> str:
        """
        Generate a random string of the given length.
        """
        out = ''.join(secrets.choice(string.ascii_letters + string.digits)
                      for _ in range(length))
        return out

    # pylint: disable=too-many-locals
    def _run_cmd_impl(self, command: str, timeout: int) -> dict:
        if not command:
            raise ValueError("command is empty")

        self._logger.info("Running command: %s", command)
        self._stop = False

        cmd = f"{command}\n"
        code = self._generate_string()
        cmd_end = f"echo $?-{code}\n"
        matcher = re.compile(f"(?P<retcode>\\d+)-{code}")

        stdout = ""
        retcode = None
        t_start = time.time()
        t_end = 0
        t_secs = max(timeout, 0)

        try:
            self._stdin.write(cmd)
            self._stdin.write(cmd_end)
            self._stdin.flush()

            while not self._stop:
                if 0 < t_secs <= time.time() - t_start:
                    raise RunnerError("Command timed out")

                line = self._stdout.readline()
                if not line:
                    continue

                if self._ignore_echo and line in [cmd, cmd_end]:
                    continue

                match = matcher.match(line)
                if match:
                    retcode = match.group("retcode")
                    t_end = time.time() - t_start
                    break

                self._logger.info(line.rstrip())

                stdout += line
        except OSError as err:
            raise RunnerError(err)

        if self._stop:
            retcode = 1
            t_end = time.time() - t_start

        ret = {
            "command": command,
            "timeout": t_secs,
            "returncode": int(retcode),
            "stdout": stdout,
            "exec_time": t_end,
        }

        self._logger.debug(ret)
        self._logger.info("Command completed")

        return ret
