"""
.. module:: ssh
    :platform: Linux
    :synopsis: SSH Runner implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import time
import logging
import socket
from paramiko import SSHClient
from paramiko import AutoAddPolicy
from paramiko import SSHException
from .base import Runner
from .base import RunnerError


class SSHRunner(Runner):
    """
    SSH Runner implementation class.
    """

    def __init__(self, **kwargs) -> None:
        """
        :param host: TCP address
        :type host: str
        :param port: TCP port
        :type port: int
        :param user: username for logging in
        :type user: str
        :param password: password for logging in
        :type password: str
        :param timeout: connection timeout
        :type timeout: int
        :param key_file: file of the SSH keys
        :type key_file: str
        :param ssh_opts: additional SSH options
        :type ssh_opts: str
        """
        self._logger = logging.getLogger("ltp.ssh")
        self._host = kwargs.get("host", "localhost")
        self._port = int(kwargs.get("port", "22"))
        self._user = kwargs.get("user", "root")
        self._timeout = int(kwargs.get("timeout", "10"))
        self._password = kwargs.get("password", None)
        self._key_file = kwargs.get("key_file", None)
        self._ssh_opts = kwargs.get("ssh_opts", None)
        self._client = SSHClient()

        if not self._host:
            raise ValueError("host is empty")

        if not self._user:
            raise ValueError("user is empty")

        if self._port <= 0 or self._port >= 65536:
            raise ValueError("port is out of range")

        if self._key_file and not os.path.isfile(self._key_file):
            raise ValueError("private key doesn't exist")

    @property
    def name(self) -> str:
        return "ssh"

    def start(self) -> None:
        try:
            self._logger.info("Loading system keys")
            self._client.load_system_host_keys()
            self._client.set_missing_host_key_policy(AutoAddPolicy())

            self._logger.info("Connecting to %s:%d", self._host, self._port)

            self._client.connect(
                self._host,
                port=self._port,
                username=self._user,
                password=self._password,
                key_filename=self._key_file,
                timeout=self._timeout)

            self._logger.info("Connected to host")
        except SSHException as err:
            raise RunnerError(err)
        except socket.error as err:
            raise RunnerError(err)
        except ValueError as err:
            raise RunnerError(err)

    def stop(self, _: int = 0) -> None:
        try:
            self._logger.info("Closing connection")
            self._client.close()
            self._logger.info("Connection closed")
        except SSHException as err:
            raise RunnerError from err

    def force_stop(self) -> None:
        self.stop()

    def _run_cmd_impl(self, command: str, timeout: int) -> dict:
        if not command:
            raise ValueError("command is empty")

        self._logger.info(
            "Executing command (timeout=%d): %s", timeout, command)

        t_secs = max(timeout, 0)
        t_start = time.time()
        t_end = 0
        retcode = 0
        stdout = None

        try:
            _, stdout, _ = self._client.exec_command(
                command,
                timeout=t_secs)
            t_end = time.time() - t_start
        except SSHException as err:
            raise RunnerError(err)
        except FileNotFoundError as err:
            # key not found
            raise RunnerError(err)

        stdout_str = "\n".join(stdout.readlines())

        retcode = -1
        if stdout:
            retcode = stdout.channel.recv_exit_status()

        ret = {
            "command": command,
            "stdout": stdout_str,
            "returncode": retcode,
            "timeout": t_secs,
            "exec_time": t_end,
        }

        self._logger.debug("return data=%s", ret)

        self._logger.info("Command executed")

        return ret
