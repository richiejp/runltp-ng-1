"""
.. module:: local
    :platform: Linux
    :synopsis: local file copy downloader implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import logging
from .base import Downloader
from .base import DownloaderError


class LocalDownloader(Downloader):
    """
    This downloader only copy files in the host machine and it's a fallback
    downloader for local tests execution.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("ltp.downloader.local")
        self._fetching = False

    def stop(self) -> None:
        self._logger.info("Stopping all current operations")
        self._fetching = False

    def fetch_file(self, target_path: str, local_path: str) -> None:
        if not target_path:
            raise ValueError("target path is empty")

        if not local_path:
            raise ValueError("local path is empty")

        if not os.path.isfile(target_path):
            raise ValueError("target file doesn't exist")

        self._logger.info("Copy '%s' to '%s'", target_path, local_path)

        self._fetching = True

        try:
            with open(target_path, 'rb') as ftarget:
                with open(local_path, 'wb+') as flocal:
                    data = ftarget.read(1024)
                    while data != b'' and self._fetching:
                        flocal.write(data)
                        data = ftarget.read(1024)
        except IOError as err:
            raise DownloaderError(err)

        if not self._fetching:
            self._logger.info("Copy stopped")
        else:
            self._logger.info("File copied")
