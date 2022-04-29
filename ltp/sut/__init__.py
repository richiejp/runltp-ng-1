"""
.. module:: __init__
    :platform: Linux
    :synopsis: SUT package definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from .base import SUT
from .base import SUTError
from .base import SUTFactory
from .local import LocalSUT
from .local import LocalSUTFactory
from .qemu import QemuSUT
from .qemu import QemuSUTFactory
from .ssh import SSHSUTFactory
from .ssh import SSHSUT

__all__ = [
    "SUT",
    "SUTError",
    "SUTFactory",
    "LocalSUT",
    "LocalSUTFactory",
    "QemuSUT",
    "QemuSUTFactory",
    "SSHSUT",
    "SSHSUTFactory",
]
