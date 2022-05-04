"""
.. module:: ssh
    :platform: Linux
    :synopsis: module defining SSH SUT

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import logging
from ltp.channel import Channel
from ltp.channel import SSHBase
from ltp.channel import SSHChannel
from .base import SUT
from .base import SUTError


class SSHSUT(SSHBase, SUT):
    """
    A SUT that is using SSH protocol con communicate and transfer data.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._logger = logging.getLogger("ltp.sut.ssh")
        self._ltpdir = kwargs.get("ltpdir", "/opt/ltp")
        self._tmpdir = kwargs.get("tmpdir", None)
        self._channel = SSHChannel(**kwargs)
        self._running = False

    @property
    def name(self) -> str:
        return "ssh"

    @property
    def channel(self) -> Channel:
        return self._channel

    def communicate(self, stdout_callback: callable = None) -> None:
        if self._running:
            raise SUTError("SUT is already running")

        self._channel.start()
        self._running = True

    def stop(self, timeout: int = 30) -> None:
        self._channel.stop(timeout=timeout)

    def force_stop(self, timeout: int = 30) -> None:
        self._channel.force_stop(timeout=timeout)
