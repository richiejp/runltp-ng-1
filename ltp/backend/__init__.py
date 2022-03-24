"""
.. module:: __init__
    :platform: Linux
    :synopsis: backend package initializer

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from .base import Backend
from .base import BackendError
from .shell import ShellBackend
from .ssh import SSHBackend
from .serial import SerialBackend

__all__ = [
    "Backend",
    "BackendError",
    "ShellBackend",
    "SSHBackend",
    "SerialBackend",
]
