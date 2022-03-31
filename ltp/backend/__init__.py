"""
.. module:: __init__
    :platform: Linux
    :synopsis: backend package definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from .base import Backend
from .base import BackendError
from .local import LocalBackend

__all__ = [
    "Backend",
    "BackendError",
    "LocalBackend",
]
