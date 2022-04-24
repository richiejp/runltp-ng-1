"""
.. module:: transport
    :platform: Linux
    :synopsis: transport downloader implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import logging
import threading
from ltp.runner import Runner
from .base import Downloader
from .base import DownloaderError


class TransportDownloader(Downloader):
    """
    The transport downloader is used by qemu to transfer data from
    virtual machine to host.
    """

    def __init__(self,
                 runner: Runner,
                 transport_dev: str,
                 transport_path: str) -> None:
        """
        :param runner: runner is used to send data into the transfer device
        :type runner: Runner
        :param transport_dev: transport device name
        :type transport_dev: str
        :param transport_path: transport file path
        :type transport_path: str
        """
        self._logger = logging.getLogger("ltp.downloader.transport")
        self._runner = runner
        self._transport_path = transport_path
        self._transport_dev = transport_dev
        self._stopped = False
        self._running = False
        self._last_pos = 0
        self._lock = threading.Lock()

        if not self._runner:
            raise ValueError("runner is empty")

        if not self._transport_dev:
            raise ValueError("transport device is empty")

        if not self._transport_path or \
                not os.path.isfile(self._transport_path):
            raise ValueError("transport file doesn't exist")

    @property
    def is_running(self) -> bool:
        return self._running

    def stop(self) -> None:
        if not self.is_running:
            return

        self._logger.info("Stopping transport download")
        self._runner.stop()
        self._stopped = True

        # pylint: disable=consider-using-with
        self._lock.acquire()
        self._logger.info("Transport download stopped")

    def fetch_file(self, target_path: str, local_path: str) -> None:
        self._logger.info("Downloading: %s -> %s", target_path, local_path)
        self._stopped = False
        self._running = True

        try:
            # check for transport device existence
            trans_dev = f"/dev/{self._transport_dev}"

            ret = self._runner.run_cmd(f"test -e {trans_dev}", 1)
            if ret["returncode"] != 0:
                raise DownloaderError(f"{trans_dev} doesn't exist on trarget")

            if self._stopped:
                return

            # check for target file existence
            ret = self._runner.run_cmd(f"test -f {target_path}", 1)
            if ret["returncode"] != 0:
                raise DownloaderError(
                    f"{target_path} doesn't exist on trarget")

            if self._stopped:
                return

            # send target file to transport device
            ret = self._runner.run_cmd(
                f"cat {target_path} > {trans_dev}", 3600)
            if ret["returncode"] != 0:
                raise DownloaderError(f"Can't send file to {trans_dev}")

            if self._stopped:
                return

            # read back data and send it to the local file path
            with open(self._transport_path, "rb") as transport:
                data = transport.read()[self._last_pos:]

                self._last_pos = transport.tell()

                with open(local_path, "wb") as flocal:
                    flocal.write(data)

            self._logger.info("File downloaded")
        finally:
            if self._stopped:
                self._lock.release()

            self._running = False
