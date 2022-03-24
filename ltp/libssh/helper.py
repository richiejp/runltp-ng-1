"""
.. module:: helper.py
    :platform: Linux
    :synopsis: helper classes using libssh

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import ctypes
import logging
from typing import Any
from ltp.libssh.constants import (
    SSH_AUTH_SUCCESS,
    SSH_OK,
    SSH_OPTIONS_HOST,
    SSH_OPTIONS_PORT,
    SSH_OPTIONS_TIMEOUT,
    SSH_OPTIONS_USER,
)
from ltp.libssh.session import (
    ssh_connect,
    ssh_disconnect,
    ssh_free,
    ssh_get_error,
    ssh_get_version,
    ssh_new,
    ssh_options_set,
    ssh_pki_import_privkey_file,
    ssh_userauth_password,
    ssh_userauth_publickey,
    ssh_userauth_publickey_auto,
    ssh_userauth_none,
    ssh_key_new,
    ssh_key_free
)
from ltp.libssh.channel import (
    ssh_channel_new,
    ssh_channel_close,
    ssh_channel_free,
    ssh_channel_open_session,
    ssh_channel_request_exec,
    ssh_channel_read_timeout,
    ssh_channel_get_exit_status
)


class SSHError(Exception):
    """
    Raised when an error occurs during SSH client session.
    """


class SSHClient:
    """
    SSH client handler.
    """

    def __init__(
            self,
            user: str,
            host: str,
            port: int = 22,
            timeout: int = 10) -> None:
        """
        :param user: username for logging in
        :type user: str
        :param host: hostname address
        :type host: str
        :param port: SSH port
        :type port: int
        :param timeout: SSH timeout
        :type timeout: int
        """
        if not user:
            raise ValueError("username is empty")

        if not host:
            raise ValueError("hostname is empty")

        if port not in range(1, 65536):
            raise ValueError("port is out of range")

        self._logger = logging.getLogger("ltp.libssh")
        self._user = user
        self._host = host
        self._port = port
        self._timeout = max(timeout, 0)
        self._session = None

    def _raise_session_error(self, msg: str = None):
        """
        Release ssh session and raises a SSHError using error message
        from libssh if a message has not specified.
        """
        if not msg:
            c_msg = ssh_get_error(self._session)
            msg = c_msg.decode()

        ssh_free(self._session)
        raise SSHError(msg)

    def _set_option(self, option: int, value: Any) -> None:
        """
        Setup a specific SSH session option.
        """
        ret = None

        if isinstance(value, int):
            c_value = ctypes.byref(ctypes.c_int(value))
            ret = ssh_options_set(
                self._session,
                option,
                c_value)
        else:
            data = ctypes.c_char_p(str(value).encode("utf-8"))
            c_value = ctypes.cast(data, ctypes.c_void_p)
            ret = ssh_options_set(
                self._session,
                option,
                c_value)

        if ret != SSH_OK:
            self._raise_session_error()

    def connect(self):
        """
        Connect to SSH server.
        """
        if self._session:
            raise SSHError("SSH session already running")

        self._logger.info(
            "Connecting to %s@%s:%s",
            self._user,
            self._host,
            self._port)

        self._session = ssh_new()

        if not self._session:
            raise SSHError("Can't create SSH session")

        version = ssh_get_version(self._session)
        self._logger.info("Protocol version: %s", version)

        self._set_option(SSH_OPTIONS_USER, self._user)
        self._set_option(SSH_OPTIONS_HOST, self._host)
        self._set_option(SSH_OPTIONS_PORT, self._port)
        self._set_option(SSH_OPTIONS_TIMEOUT, self._timeout * 1000)

        ret = ssh_connect(self._session)
        if ret != SSH_OK:
            self._raise_session_error()

        self._logger.info("Connection started")

    def disconnect(self):
        """
        Disconnect from SSH server.
        """
        if not self._session:
            return

        self._logger.info("Closing connection")

        ssh_disconnect(self._session)
        ssh_free(self._session)
        self._session = None

        self._logger.info("Connection closed")

    def userauth_none(self):
        """
        Authenticate with none authentication.
        """
        self._logger.info("Using none authentication")

        ret = ssh_userauth_none(self._session, None)
        if ret != SSH_AUTH_SUCCESS:
            self._raise_session_error()

    def userauth_publickey_auto(self) -> None:
        """
        Authenticate using default public key.
        """
        self._logger.info("Using default private key authentication")

        ret = ssh_userauth_publickey_auto(self._session, None, None)
        if ret != SSH_AUTH_SUCCESS:
            self._raise_session_error()

    def userauth_privkey(self, privkey: str, passphrase: str) -> None:
        """
        Authenticate using private key.
        :param privkey: private key absolute path.
        :type privkey: str
        :param passphrase: private key passphrase.
        :type passphrase: str
        """
        if not privkey:
            raise ValueError("Private key is empty")

        self._logger.info("Using private key authentication")

        c_keyfile = ctypes.c_char_p(privkey.encode("utf-8"))

        c_passphrase = None
        if passphrase:
            c_passphrase = ctypes.c_char_p(passphrase.encode("utf-8"))

        c_privkey = ssh_key_new()
        ret = ssh_pki_import_privkey_file(
            c_keyfile,
            c_passphrase,
            None,
            None,
            ctypes.byref(c_privkey))

        if ret != SSH_OK:
            self._raise_session_error(
                "Failed to import private key "
                "(incorrect password or invalid file)")

        ret = ssh_userauth_publickey(self._session, None, c_privkey)
        if ret != SSH_AUTH_SUCCESS:
            self._raise_session_error()

        ssh_key_free(c_privkey)

    def userauth_password(self, password: str) -> None:
        """
        Authenticate using username/password.
        :param password: authentication password.
        :type password: str
        """
        if not password:
            raise ValueError("Password is empty")

        self._logger.info("Using password authentication")

        c_password = ctypes.c_char_p(password.encode("utf-8"))

        ret = ssh_userauth_password(self._session, None, c_password)
        if ret != SSH_AUTH_SUCCESS:
            self._raise_session_error()

    def execute(self, command: str, timeout: int = 60) -> set:
        """
        Execute a command on remote server.
        :param command: command to execute.
        :type command: str
        :param timeout: command response timeout in seconds (default is 60)
        :type timeout: int
        :returns: couple of (int, str) defining exit_status and stdout
        """
        self._logger.info(
            "Executing remote command '%s' (timeout=%ds)",
            command, timeout)

        if not command:
            raise ValueError("Command is empty")

        c_channel = ssh_channel_new(self._session)
        if not c_channel:
            raise SSHError("Can't create communication channel")

        def raise_error(close: bool) -> None:
            """
            Release channel and raises a SSHError using libssh error message.
            """
            c_msg = ssh_get_error(self._session)
            msg = c_msg.decode()

            if close:
                ssh_channel_close(c_channel)

            ssh_channel_free(c_channel)
            raise SSHError(msg)

        ret = ssh_channel_open_session(c_channel)
        if ret != SSH_OK:
            raise_error(False)

        c_command = ctypes.c_char_p(command.encode())
        ret = ssh_channel_request_exec(c_channel, c_command)
        if ret != SSH_OK:
            raise_error(True)

        stdout = ""
        nbytes = 1
        buffsize = 1024
        data = ctypes.create_string_buffer(buffsize)

        while nbytes > 0:
            nbytes = ssh_channel_read_timeout(
                c_channel,
                data,
                buffsize,
                0,
                timeout * 1000)

            if nbytes < 0:
                raise_error(True)

            stdout += data.value[:nbytes].decode("utf-8")

        exit_status = ssh_channel_get_exit_status(c_channel)

        ssh_channel_close(c_channel)
        ssh_channel_free(c_channel)

        self._logger.info("Command executed")

        return exit_status, stdout
