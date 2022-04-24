"""
.. module:: base
    :platform: Linux
    :synopsis: module containing downloader definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ltp import LTPException


class DownloaderError(LTPException):
    """
    Raised when an error occurs during download.
    """


class Downloader:
    """
    A downloader is used to download files from target to local host.
    """

    @property
    def is_running(self) -> bool:
        """
        Return True if object is running.
        """
        raise NotImplementedError()

    def fetch_file(self, target_path: str, local_path: str) -> None:
        """
        Fetch file from target path and download it in the specified
        local path.
        :param target_path: path of the file to download from target
        :type target_path: str
        :param local_path: path of the downloaded file on local host
        :type local_path: str
        """
        raise NotImplementedError()

    def stop(self) -> None:
        """
        Stop downloading.
        """
        raise NotImplementedError()
