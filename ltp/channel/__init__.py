"""
.. module:: __init__
    :platform: Linux
    :synopsis: channel package initializer

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from .base import Channel
from .base import ChannelError
from .ssh import SSHBase
from .ssh import SSHChannel
from .shell import ShellChannel
from .serial import SerialChannel

__all__ = [
    "Channel",
    "ChannelError",
    "SSHBase",
    "SSHChannel",
    "ShellChannel",
    "SerialChannel"
]
