"""
.. module:: serial
    :platform: Linux
    :synopsis: module containing serial Runner definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import re
import time
import string
import signal
import secrets
import logging
import threading
from ltp.common.freader import IOReader
from .base import SUTError
from .base import SUTTimeoutError


# pylint: disable=too-many-instance-attributes
class CommandPrompt:
    """
    Used to communicate with file descriptors exposing a command prompt.
    """

    def __init__(self, **kwargs) -> None:
        """
        :param stdin: standard input file handler
        :type stdin: IO
        :param stdout: standard output file handler
        :type stdout: IO
        :param ignore_echo: if True, echoed commands will be ignored
        :type ignore_echo: bool
        """
        self._logger = logging.getLogger("ltp.sut.prompt")
        self._stdin = kwargs.get("stdin", None)
        self._stdout = kwargs.get("stdout", None)
        self._ignore_echo = kwargs.get("ignore_echo", True)

        if not self._stdin:
            raise ValueError("stdin is empty")

        if not self._stdout:
            raise ValueError("stdout is empty")

        self._stop = False
        self._last_pos = 0
        self._initialized = False
        self._running_command = False
        self._stop_lock = threading.Lock()
        self._cmd_lock = threading.Lock()
        self._reader = IOReader(self._stdout.fileno())
        self._ps1 = f"#{self._generate_string()}#"

    @property
    def is_running(self) -> bool:
        """
        True if command is running. False otherwise.
        """
        return self._running_command

    def start(self) -> None:
        """
        Initialize prompt.
        """
        if self._initialized:
            return

        self._init_prompt()
        self._initialized = True

    def stop(self, timeout: int = 30) -> None:
        """
        Stop the current running command.
        """
        if not self.is_running:
            return

        with self._stop_lock:
            self._stop_running_command(timeout)

    def _wait_prompt(self, timeout: int = 15) -> None:
        """
        Read stdout until prompt shows up.
        """
        self._logger.info("Waiting for command prompt")

        self._stdin.write('\n')
        self._stdin.flush()

        start_t = time.time()

        stdout = self._reader.read_until(
            lambda x: x.endswith(f"\n{self._ps1}"),
            start_t,
            timeout,
            self._logger.debug)

        if not stdout:
            if time.time() - start_t >= timeout:
                raise SUTTimeoutError("Prompt is not replying")

            raise SUTError("Prompt is not available")

    def _init_prompt(self) -> None:
        """
        Initialize shell prompt.
        """
        self._logger.info("Initializing command prompt")

        self._stdin.write(f"export PS1='{self._ps1}'\n")
        self._stdin.flush()

        self._wait_prompt(timeout=5)

    def _send_ctrl_c(self) -> None:
        """
        Send CTRL+C to stop any current command execution.
        """
        self._logger.info("Sending CTRL+C")
        self._stdin.write('\x03')
        self._stdin.flush()

    def _wait_for_stop(self, timeout: int = 30):
        """
        Wait until command ends.
        """
        secs = max(timeout, 0)
        start_t = time.time()

        while self.is_running:
            if time.time() - start_t > secs:
                raise SUTError("Stop timed out after 30 seconds")

    def _stop_running_command(self, timeout: int) -> None:
        """
        Stop the running command.
        """
        if not self._running_command:
            return

        self._logger.info("Stopping command")

        self._stop = True
        self._send_ctrl_c()
        self._wait_prompt(timeout=timeout)

        self._wait_for_stop(timeout=timeout)

        self._logger.info("Command stopped")

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
        code = self._generate_string()
        cmd_end = f"echo $?-{code}"
        matcher = re.compile(f"^(?P<retcode>\\d+)-{code}")

        stdout = ""
        retcode = -1
        t_start = time.time()
        t_secs = max(timeout, 0)
        t_end = 0

        self._stdin.write(cmd)
        self._stdin.write('\n')
        self._stdin.write(cmd_end)
        self._stdin.write('\n')
        self._stdin.flush()

        while True:
            line = self._reader.read_until(
                lambda x: x.endswith('\n'),
                t_start,
                t_secs,
                self._logger.debug)

            if self._reader.timed_out:
                self._send_ctrl_c()
                self._wait_prompt(timeout=10)

                raise SUTTimeoutError(
                    f"'{cmd}' command timed out (timeout={timeout})")

            if self._stop:
                break

            if self._ignore_echo:
                if cmd in line or cmd_end in line:
                    continue

            match = matcher.match(line)
            if match:
                retcode_str = match.group("retcode")
                self._logger.debug("rercode=%s", retcode_str)

                retcode = int(retcode_str)
                t_end = time.time() - t_start
                break

            if stdout_callback:
                stdout_callback(line.rstrip())

            stdout += line

        if self._stop:
            retcode = signal.SIGTERM

        t_end = time.time() - t_start

        return retcode, t_end, stdout

    def execute(self,
                command: str,
                timeout: int = 3600,
                cwd: str = None,
                env: dict = None,
                stdout_callback: callable = None) -> dict:
        """
        Execute a command on prompt.
        :param command: command to execute
        :param timeout: timeout before stopping execution. Default is 3600
        :type timeout: int
        :param cwd: current working directory
        :type cwd: str
        :param env: environment variables
        :type env: dict
        :param stdout_callback: callback that can be used to get stdout lines
            in realtime.
        :type stdout_callback: callable
        :returns: retcode (int), t_end (float), stdout (str)
        """
        if not command:
            raise ValueError("command is empty")

        retcode = -1
        t_end = 0
        stdout = ""

        with self._cmd_lock:
            self._logger.info("Running command: %s", command)
            self._stop = False

            cmd = ""
            if cwd:
                cmd = f"cd {cwd} && "

            if env:
                for key, value in env.items():
                    cmd += f"export {key}={value} && "

            cmd += command

            try:
                self._running_command = True

                retcode, t_end, stdout = self._send(
                    cmd,
                    timeout,
                    stdout_callback=stdout_callback)

                self._logger.debug("retcode=%d", retcode)
                self._logger.debug("t_end=%f", t_end)
                self._logger.debug("stdout=%s", stdout)

                self._logger.info("Command completed")
            except OSError as err:
                raise SUTError(err)
            finally:
                self._stop = False
                self._running_command = False

        return retcode, t_end, stdout
