"""
.. module:: serial
    :platform: Linux
    :synopsis: module containing serial Runner definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import re
import time
import string
import signal
import secrets
import logging
import threading
from ltp.common.freader import IOReader
from .base import Channel
from .base import ChannelError
from .base import ChannelTimeoutError


# pylint: disable=too-many-instance-attributes
class SerialChannel(Channel):
    """
    This is not a standard serial I/O protocol communication class, but rather
    a helper class for sessions where a serial hw channel is exposed via file
    descriptor. This is really common in a qemu session, where console is
    exposed in the host system via file descriptor.
    """

    def __init__(self, **kwargs) -> None:
        """
        :param stdin: standard input file handler
        :type stdin: IO
        :param stdout: standard output file handler
        :type stdout: IO
        :param transport_dev: transport device path
        :type transport_dev: str
        :param transport_path: transport file path
        :type transport_path: str
        :param ignore_echo: if True, echoed commands will be ignored
        :type ignore_echo: bool
        """
        self._logger = logging.getLogger("ltp.channel.serial")
        self._stdin = kwargs.get("stdin", None)
        self._stdout = kwargs.get("stdout", None)
        self._transport_dev = kwargs.get("transport_dev", None)
        self._transport_path = kwargs.get("transport_path", None)
        self._ignore_echo = kwargs.get("ignore_echo", True)

        if not self._stdin:
            raise ValueError("stdin is empty")

        if not self._stdout:
            raise ValueError("stdout is empty")

        if not self._transport_dev:
            raise ValueError("transport device is empty")

        if not self._transport_path or \
                not os.path.isfile(self._transport_path):
            raise ValueError("transport file doesn't exist")

        self._stop = False
        self._last_pos = 0
        self._initialized = False
        self._fetching_data = False
        self._running_command = False
        self._stop_lock = threading.Lock()
        self._cmd_lock = threading.Lock()
        self._fetch_lock = threading.Lock()
        self._reader = IOReader(self._stdout.fileno())
        self._ps1 = f"#{self._generate_string()}#"

    @property
    def is_running(self) -> bool:
        return self._fetching_data or self._running_command

    def start(self) -> None:
        if self._initialized:
            return

        self._init_prompt()
        self._initialized = True

    def stop(self, timeout: int = 30) -> None:
        if not self.is_running:
            return

        with self._stop_lock:
            self._stop_running_command(timeout)
            self._stop_fetching_data(timeout)

    def force_stop(self, timeout: int = 30) -> None:
        self.stop(timeout=timeout)

    def _init_prompt(self) -> None:
        """
        Initialize shell prompt.
        """
        self._logger.info("Initializing command prompt")

        self._stdin.write(f"export PS1='{self._ps1}'\n")
        self._stdin.flush()

        self._wait_prompt()

    def _wait_prompt(self) -> None:
        """
        Read stdout until prompt shows up.
        """
        self._logger.info("Waiting for command prompt")

        self._stdin.write('\n')
        self._stdin.flush()

        stdout = self._reader.read_until(
            lambda x: x.endswith(f"\n{self._ps1}"),
            time.time(), 15,
            self._logger.debug)

        if not stdout:
            raise ChannelError("Prompt is not available")

    def _send_ctrl_c(self) -> None:
        """
        Send CTRL+C to stop any current command execution.
        """
        self._logger.info("Sending CTRL+C")
        self._stdin.write('\x03')
        self._stdin.flush()

    def _stop_running_command(self, timeout: int) -> None:
        """
        Stop the running command.
        """
        if not self._running_command:
            return

        self._logger.info("Stopping command")

        self._stop = True
        self._send_ctrl_c()
        self._wait_for_stop(timeout=timeout)

        self._wait_prompt()

        self._logger.info("Command stopped")

    def _stop_fetching_data(self, timeout: int) -> None:
        """
        Stop fetching data.
        """
        if not self._fetching_data:
            return

        self._logger.info("Stop fetching data")

        self._stop = True
        self._wait_for_stop(timeout=timeout)

        self._logger.info("Fetching data stopped")

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

            if not line:
                self._send_ctrl_c()
                self._wait_prompt()

                raise ChannelTimeoutError(
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

    def run_cmd(self,
                command: str,
                timeout: int = 3600,
                cwd: str = None,
                env: dict = None,
                stdout_callback: callable = None) -> dict:
        if not command:
            raise ValueError("command is empty")

        ret = None

        with self._cmd_lock:
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

            cmd += command

            try:
                self._running_command = True

                retcode, t_end, stdout = self._send(
                    cmd, timeout, stdout_callback)

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
                raise ChannelError(err)
            finally:
                self._stdin.flush()
                self._stop = False
                self._running_command = False

        return ret

    def fetch_file(
            self,
            target_path: str,
            local_path: str,
            timeout: int = 3600) -> None:
        if not target_path:
            raise ValueError("target path is empty")

        if not local_path:
            raise ValueError("local path is empty")

        with self._fetch_lock:
            self._logger.info("Downloading: %s -> %s", target_path, local_path)
            self._stop = False
            self._fetching_data = True

            try:
                ret = self.run_cmd(
                    f"cat {target_path} > {self._transport_dev}",
                    timeout=timeout)

                if ret["returncode"] not in [0, signal.SIGTERM]:
                    stdout = ret["stdout"]
                    raise ChannelError(
                        f"Can't send file to {self._transport_dev}: {stdout}")

                if self._stop:
                    return

                # read back data and send it to the local file path
                file_size = os.path.getsize(self._transport_path)
                start_t = time.time()

                with open(self._transport_path, "rb") as transport:
                    with open(local_path, "wb") as flocal:
                        while not self._stop and self._last_pos < file_size:
                            if time.time() - start_t >= timeout:
                                self._logger.info(
                                    "Transfer timed out after %d seconds",
                                    timeout)

                                raise ChannelTimeoutError(
                                    "Timeout during transfer "
                                    f"(timeout={timeout}):"
                                    f" {target_path} -> {local_path}")

                            time.sleep(0.05)

                            transport.seek(self._last_pos)
                            data = transport.read(4096)

                            self._last_pos = transport.tell()

                            flocal.write(data)

                self._logger.info("File downloaded")
            finally:
                self._stop = False
                self._fetching_data = False
