"""
.. module:: scp
    :platform: Linux
    :synopsis: scp downloader implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from scp import SCPClient
from scp import SCPException
from ltp.common.ssh import SSH
from ltp.common.ssh import SSHError
from .base import Downloader
from .base import DownloaderError


class SCPDownloader(SSH, Downloader):
    """
    Downloader using SCP protocol.
    """

    def stop(self, _: int = 0) -> None:
        try:
            self.disconnect()
        except SSHError as err:
            raise DownloaderError(err)

    def fetch_file(self, target_path: str, local_path: str) -> None:
        if not target_path:
            raise ValueError("target path is empty")

        if not local_path:
            raise ValueError("local path is empty")

        self._stop = False

        try:
            self.connect()
        except ValueError as err:
            raise DownloaderError(err)

        with SCPClient(self._client.get_transport()) as scp:
            try:
                scp.get(target_path, local_path=local_path)
            except SCPException as err:
                if self._stop and scp.channel.closed:
                    return
                raise DownloaderError(err)
