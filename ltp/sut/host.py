"""
.. module:: local
    :platform: Linux
    :synopsis: module containing SUT definition for host testing execution

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ltp.channel import Channel
from ltp.channel import ShellChannel
from .base import SUT
from .base import SUTError


class HostSUT(SUT):
    """
    SUT implementation for host testing.
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
        if not self._channel:
            return

        self._channel.stop(timeout=timeout)
        self._channel = None

    def force_stop(self, timeout: int = 30) -> None:
        if not self._channel:
            return

        self._channel.force_stop(timeout=timeout)
        self._channel = None
