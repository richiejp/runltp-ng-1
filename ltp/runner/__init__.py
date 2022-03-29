"""
.. module:: __init__
    :platform: Linux
    :synopsis: runner package initializer

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from .base import Runner
from .base import RunnerError
from .shell import ShellRunner
from .ssh import SSHRunner
from .serial import SerialRunner

__all__ = [
    "Runner",
    "RunnerError",
    "ShellRunner",
    "SSHRunner",
    "SerialRunner",
]
