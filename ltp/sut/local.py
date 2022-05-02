"""
.. module:: local
    :platform: Linux
    :synopsis: module containing SUT definition for local testing execution

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ltp.channel import Channel
from ltp.channel import ShellChannel
from .base import SUT
from .base import SUTError
from .base import SUTFactory


class LocalSUT(SUT):
    """
    Local SUT implementation for host testing.
    """

    def __init__(self) -> None:
        self._channel = None

    @property
    def name(self) -> str:
        return "host"

    @property
    def channel(self) -> Channel:
        return self._channel

    def communicate(self, stdout_callback: callable = None) -> None:
        if self._channel:
            raise SUTError("SUT is already running")

        self._channel = ShellChannel()

    def stop(self, timeout: int = 30) -> None:
        self._channel.stop(timeout=timeout)

    def force_stop(self, timeout: int = 30) -> None:
        self._channel.force_stop(timeout=timeout)


class LocalSUTFactory(SUTFactory):
    """
    LocalSUT factory class.
    """

    def create(self) -> SUT:
        sut = LocalSUT()
        return sut
