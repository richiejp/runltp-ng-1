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
from paramiko import RSAKey
from scp import SCPClient
from scp import SCPException
from ltp import LTPException


class SSHError(LTPException):
    """
    Raised when something got wrong in the SSH communication class.
    """


class SSHBase:
    """
    Base class for each class using SSH.
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


class SSH(SSHBase):
    """
    Class to communicate via SSH protocol.
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
        super().__init__(**kwargs)
        self._stop = False

    def connect(self) -> None:
        """
        Connect to host via SSH protocol.
        """
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
                pkey=RSAKey.from_private_key_file(self._key_file),
                timeout=self._timeout)

            self._logger.info("Connected to host")
        except SSHException as err:
            raise SSHError(err)
        except socket.error as err:
            raise SSHError(err)
        except ValueError as err:
            raise SSHError(err)

    def disconnect(self) -> None:
        """
        Disconnect from host.
        """
        try:
            self._logger.info("Closing connection")
            self._stop = True
            self._client.close()
            self._logger.info("Connection closed")
        except SSHException as err:
            raise SSHError from err

    # pylint: disable=too-many-locals
    def execute(self,
                command: str,
                timeout: int = 3600,
                cwd: str = None,
                env: dict = None,
                stdout_callback: callable = None) -> dict:
        """
        Execute a command on host.
        :param command: command to execute
        :type command: str
        :param timeout: command timeout
        :type timeout: int
        :param cwd: current working directory
        :type cwd: str
        :param env: environment variables
        :type env: dict
        :param stdout_callback: callback that can be used to get stdout lines
            in realtime.
        :type stdout_callback: callable
        :returns: dictionary containing command execution information

            {
                "command": <str>,
                "timeout": <int>,
                "returncode": <int>,
                "stdout": <str>,
                "exec_time": <int>,
                "cwd": <str>,
                "env": <dict>,
            }

        """
        if not command:
            raise ValueError("command is empty")

        self._logger.info(
            "Executing command (timeout=%d): %s", timeout, command)

        t_secs = max(timeout, 0)
        t_start = time.time()
        t_end = 0
        retcode = -1
        stdout_str = ""

        try:
            cmd = ""
            if cwd:
                cmd = f"cd {cwd} && "

            # environment can't be set by exec_command, since it requires
            # a server side setup enabling AcceptEnv, so we apply them with
            # the command
            if env:
                for key, value in env.items():
                    cmd += f"export {key}={value} && "

            cmd += command

            _, stdout, _ = self._client.exec_command(
                cmd,
                timeout=t_secs)

            while True:
                line = stdout.readline()
                if not line:
                    break

                if stdout_callback:
                    stdout_callback(line.rstrip())

                self._logger.info(line.rstrip())
                stdout_str += line

            t_end = time.time() - t_start
            retcode = stdout.channel.recv_exit_status()
        except SSHException as err:
            raise SSHError(err)
        except FileNotFoundError as err:
            # key not found
            raise SSHError(err)

        ret = {
            "command": command,
            "stdout": stdout_str,
            "returncode": retcode,
            "timeout": t_secs,
            "exec_time": t_end,
            "cwd": cwd,
            "env": env,
        }

        self._logger.debug("return data=%s", ret)
        self._logger.info("Command executed")

        return ret

    def get(self, target_path: str, local_path: str) -> None:
        """
        Fetch file from host.
        : param target_path: file on target
        : type target_path: str
        : param local_path: file on local host
        : type local_path: str
        """
        if not target_path:
            raise ValueError("target path is empty")

        if not local_path:
            raise ValueError("local path is empty")

        self._stop = False

        self._logger.info("Transfer file: %s -> %s", target_path, local_path)

        with SCPClient(self._client.get_transport()) as scp:
            try:
                scp.get(target_path, local_path=local_path)
            except SCPException as err:
                if self._stop and scp.channel.closed:
                    return
                raise SSHError(err)

        self._logger.info("File transfer completed")
