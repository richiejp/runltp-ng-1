"""
.. module:: serial
    :platform: Linux
    :synopsis: module containing serial Runner definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import time
import string
import secrets
import logging
from .base import Runner
from .base import RunnerError


class SerialRunner(Runner):
    """
    This is not a standard serial I/O protocol communication class, but rather
    a helper class for sessions where a serial hw channel is exposed via file
    descriptor. This is really common in a qemu session, where console is
    mounted in the host system via file descriptor.
    """

    def __init__(self, target: str) -> None:
        """
        :param target: file where reading/writing data
        :type target: str
        """
        self._logger = logging.getLogger("ltp.Runner.serial")
        self._target = target
        self._file = None

        if not os.path.isfile(self._target):
            raise ValueError("target file doesn't exist")

    @property
    def name(self) -> str:
        return "serial"

    # pylint: disable=consider-using-with
    def start(self) -> None:
        self._logger.info("Opening target file: %s", self._target)

        try:
            self._file = open(self._target, 'w+', encoding="utf-8")
        except OSError as err:
            raise RunnerError(err)

        self._logger.info("Target file is opened")

    def stop(self, _: int = 0) -> None:
        if not self._file:
            return

        self._logger.info("Closing target file: %s", self._target)
        self._file.close()
        self._logger.info("Target file is closed")

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

    def _run_cmd_impl(self, command: str, timeout: int) -> dict:
        if not command:
            raise ValueError("command is empty")

        self._logger.info("Running command: %s", command)

        cmd = f"{command}\n"
        code = self._generate_string()
        cmd_end = f"echo $?-{code}\n"

        stdout = ""
        ending = None
        start_t = time.time()
        t_secs = max(timeout, 0)

        try:
            self._file.flush()
            self._file.write(cmd)
            self._file.write(cmd_end)

            while True:
                if 0 < t_secs <= time.time() - start_t:
                    raise RunnerError("Command timed out")

                line = self._file.readline()
                if not line:
                    continue

                self._logger.debug("stdout: %s", line.rstrip())
                if code in line:
                    ending = line
                    break

                stdout += line
        except OSError as err:
            raise RunnerError(err)

        result = ending.split('-')
        ret = {
            "command": command,
            "timeout": t_secs,
            "returncode": int(result[0]),
            "stdout": stdout
        }

        self._logger.debug(ret)
        self._logger.info("Command completed")

        return ret
