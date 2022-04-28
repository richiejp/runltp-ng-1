"""
.. module:: scp
    :platform: Linux
    :synopsis: scp downloader implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ltp.common.ssh import SSH
from ltp.common.ssh import SSHError
from .base import Downloader
from .base import DownloaderError


class SCPDownloader(SSH, Downloader):
    """
    Downloader using SCP protocol.
    """

    def stop(self) -> None:
        try:
            self.disconnect()
        except SSHError as err:
            raise DownloaderError(err)

    def fetch_file(self, target_path: str, local_path: str) -> None:
        self.get(target_path, local_path)
