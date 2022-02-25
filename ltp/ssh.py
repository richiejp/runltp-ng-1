"""
.. module:: ssh
    :platform: Linux
    :synopsis: SSH backend implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import logging
from paramiko import SSHClient
from paramiko import AutoAddPolicy
from paramiko import SSHException
from .backend import Backend
from .backend import BackendError


class SSHBackend(Backend):
    """
    SSH backend implementation class.
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

        self._logger.debug(
            "host=%s\n"
            "port=%d\n"
            "user=%s\n"
            "timeout=%d\n"
            "key_file=%s\n"
            "ssh_opts='%s'\n",
            self._host,
            self._port,
            self._user,
            self._timeout,
            self._key_file,
            self._ssh_opts)

    @property
    def name(self) -> str:
        return "ssh"

    def start(self) -> None:
        self._logger.info("Loading system keys")
        self._client.load_system_host_keys()
        self._client.set_missing_host_key_policy(AutoAddPolicy())

        self._logger.info("Connecting to %s:%d", self._host, self._port)
        try:
            self._client.connect(
                self._host,
                port=self._port,
                username=self._user,
                password=self._password,
                key_filename=self._key_file,
                timeout=self._timeout)
        except SSHException as err:
            raise BackendError from err

    def stop(self, _: int = 0) -> None:
        self._logger.info("Closing connection")
        self._client.close()
        self._logger.info("Connection closed")

    def force_stop(self) -> None:
        self.stop()

    def _run_cmd_impl(self, command: str, timeout: int) -> dict:
        if not command:
            raise ValueError("command is empty")

        t_secs = max(timeout, 0)

        self._logger.info("Executing '%s' (timeout=%d)", command, t_secs)

        stdout = None
        try:
            _, stdout, _ = self._client.exec_command(
                command,
                timeout=t_secs)
        except SSHException as err:
            raise BackendError from err
        except FileNotFoundError as err:
            # key not found
            raise BackendError from err

        stdout_str = "\n".join(stdout.readlines())
        self._logger.debug("stdout=%s", stdout_str)

        retcode = -1
        if stdout:
            retcode = stdout.channel.recv_exit_status()

        ret = {
            "command": command,
            "stdout": stdout_str,
            "returncode": retcode,
            "timeout": timeout,
        }

        self._logger.debug("return data=%s", ret)
        self._logger.info("Command executed")

        return ret
