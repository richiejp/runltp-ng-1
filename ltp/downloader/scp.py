"""
.. module:: scp
    :platform: Linux
    :synopsis: scp downloader implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import socket
import logging
from paramiko import SSHClient
from paramiko import AutoAddPolicy
from paramiko import SSHException
from scp import SCPClient
from scp import SCPException
from .base import Downloader
from .base import DownloaderError


class SCPDownloader(Downloader):
    """
    Downloader using SCP protocol.
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
        self._logger = logging.getLogger("ltp.downloader.scp")
        self._host = kwargs.get("host", "localhost")
        self._port = int(kwargs.get("port", "22"))
        self._user = kwargs.get("user", "root")
        self._timeout = int(kwargs.get("timeout", "10"))
        self._password = kwargs.get("password", None)
        self._key_file = kwargs.get("key_file", None)
        self._ssh_opts = kwargs.get("ssh_opts", None)
        self._client = SSHClient()
        self._stop = False

        if not self._host:
            raise ValueError("host is empty")

        if not self._user:
            raise ValueError("user is empty")

        if self._port <= 0 or self._port >= 65536:
            raise ValueError("port is out of range")

        if self._key_file and not os.path.isfile(self._key_file):
            raise ValueError("private key doesn't exist")

    def _connect(self) -> None:
        """
        Connect to the host using different authentication methods.
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
                key_filename=self._key_file,
                timeout=self._timeout)

            self._logger.info("Connected to host")
        except SSHException as err:
            raise DownloaderError(err)
        except socket.error as err:
            raise DownloaderError(err)
        except ValueError as err:
            raise DownloaderError(err)

    def stop(self, _: int = 0) -> None:
        try:
            self._logger.info("Closing connection")
            self._stop = True
            self._client.close()
            self._logger.info("Connection closed")
        except SSHException as err:
            raise DownloaderError(err)

    def fetch_file(self, target_path: str, local_path: str) -> None:
        if not target_path:
            raise ValueError("target path is empty")

        if not local_path:
            raise ValueError("local path is empty")

        self._stop = False
        self._connect()

        with SCPClient(self._client.get_transport()) as scp:
            try:
                scp.get(target_path, local_path=local_path)
            except SCPException as err:
                if self._stop and scp.channel.closed:
                    return
                raise DownloaderError(err)
