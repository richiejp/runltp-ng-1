"""
.. module:: ssh
    :platform: Linux
    :synopsis: SSH Runner implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import logging
from ltp.libssh.helper import SSHClient, SSHError
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
        :param key_file: private key file path
        :type key_file: str
        :param key_passphrase: private key passphrase
        :type key_passphrase: str
        :param ssh_opts: additional SSH options
        :type ssh_opts: str
        """
        self._logger = logging.getLogger("ltp.runner.ssh")
        self._password = kwargs.get("password", None)
        self._key_file = kwargs.get("key_file", None)
        self._key_passphrase = kwargs.get("key_passphrase", None)
        self._authenticated = False

        if self._key_file and not os.path.isfile(self._key_file):
            raise ValueError("private key doesn't exist")

        user = kwargs.get("user", None)
        host = kwargs.get("host", None)
        port = int(kwargs.get("port", 22))
        timeout = int(kwargs.get("timeout", 10))

        self._ssh = SSHClient(user, host, port, timeout)

        self._logger.debug(
            "host=%s\n"
            "port=%s\n"
            "user=%s\n"
            "timeout=%s\n"
            "key_file=%s\n",
            host,
            port,
            user,
            timeout,
            self._key_file)

    @property
    def name(self) -> str:
        return "ssh"

    def start(self) -> None:
        try:
            self._ssh.connect()

            if self._password:
                self._ssh.userauth_password(self._password)
            elif self._key_file:
                self._ssh.userauth_privkey(
                    self._key_file,
                    self._key_passphrase)
            else:
                raise RunnerError(
                    "Authentication method is not supported. "
                    "Please use pubkey or password authentication.")

            self._authenticated = True
        except SSHError as err:
            raise RunnerError(err)

    def stop(self, _: int = 0) -> None:
        if not self._authenticated:
            return

        self._ssh.disconnect()

    def force_stop(self) -> None:
        self.stop()

    def _run_cmd_impl(self, command: str, timeout: int) -> dict:
        if not command:
            raise ValueError("command is empty")

        t_secs = max(timeout, 0)
        retcode = 0
        stdout = None

        try:
            retcode, stdout = self._ssh.execute(command, t_secs)
        except SSHError as err:
            raise RunnerError(err)

        self._logger.debug("retcode=%d", retcode)
        self._logger.debug("stdout=%s", stdout)

        ret = {
            "command": command,
            "stdout": stdout,
            "returncode": retcode,
            "timeout": t_secs,
        }

        self._logger.debug("return data=%s", ret)

        return ret
