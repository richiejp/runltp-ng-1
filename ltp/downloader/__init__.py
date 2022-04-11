"""
.. module:: __init__
    :platform: Linux
    :synopsis: downloader package initializer

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from .base import Downloader
from .base import DownloaderError
from .local import LocalDownloader
from .transport import TransportDownloader

__all__ = [
    "Downloader",
    "DownloaderError",
    "LocalDownloader",
    "TransportDownloader",
]
