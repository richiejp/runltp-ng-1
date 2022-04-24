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
import threading
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
        self._lock = threading.Lock()
        self._stop = False
        self._running = False

        if not self._stdin:
            raise ValueError("stdin is empty")

        if not self._stdout:
            raise ValueError("stdout is empty")

    @property
    def is_running(self) -> bool:
        return self._running

    # pylint: disable=consider-using-with
    def start(self) -> None:
        pass

    def stop(self) -> None:
        if not self.is_running:
            return

        self._logger.info("Stopping command")
        self._stop = True
        self._lock.acquire()
        self._logger.info("Command stopped")

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

    def _send(self,
              cmd: str,
              timeout: int,
              stdout_callback: callable = None) -> set:
        """
        Send a command and return retcode, elabsed time and stdout.
        """
        t_secs = max(timeout, 0)

        code = self._generate_string()
        cmd_end = f"echo $?-{code}\n"
        matcher = re.compile(f"(?P<retcode>\\d+)-{code}")

        stdout = ""
        retcode = -1
        t_start = time.time()
        t_end = 0

        self._stdin.write(cmd)
        self._stdin.write(cmd_end)
        self._stdin.flush()

        # always run the command until the end because we dont have a way
        # to send CTRL+C to command via serial port
        while True:
            if 0 < t_secs <= time.time() - t_start:
                raise RunnerError("Command timed out")

            line = self._stdout.readline()
            if not line:
                continue

            if self._ignore_echo and line in [cmd, cmd_end]:
                continue

            match = matcher.match(line)
            if match:
                retcode = int(match.group("retcode"))
                t_end = time.time() - t_start
                break

            if stdout_callback:
                stdout_callback(line.rstrip())

            self._logger.info(line.rstrip())

            stdout += line

        if self._stop:
            retcode = -1

        t_end = time.time() - t_start

        return retcode, t_end, stdout

    def run_cmd(self,
                command: str,
                timeout: int = 3600,
                cwd: str = None,
                env: dict = None,
                stdout_callback: callable = None) -> dict:
        if not command:
            raise ValueError("command is empty")

        self._logger.info("Running command: %s", command)
        self._stop = False

        t_secs = max(timeout, 0)
        retcode = -1
        t_end = 0
        stdout = ""

        cmd = ""
        if cwd:
            cmd = f"cd {cwd} && "

        if env:
            for key, value in env.items():
                cmd += f"export {key}={value} && "

        cmd += f"{command}\n"
        ret = None

        try:
            self._running = True

            retcode, t_end, stdout = self._send(cmd, timeout, stdout_callback)

            ret = {
                "command": command,
                "timeout": t_secs,
                "returncode": int(retcode),
                "stdout": stdout,
                "exec_time": t_end,
                "env": env,
                "cwd": cwd,
            }

            self._logger.debug(ret)
            self._logger.info("Command completed")
        except OSError as err:
            raise RunnerError(err)
        finally:
            self._stdin.flush()
            if self._stop:
                self._lock.release()

            self._running = False

        return ret
