"""
.. module:: __init__
    :platform: Linux
    :synopsis: dispatcher package initializer

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from .base import Dispatcher
from .base import DispatcherError
from .serial import SerialDispatcher

__all__ = [
    "Dispatcher",
    "DispatcherError",
    "SerialDispatcher",
]
