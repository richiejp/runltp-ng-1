"""
.. module:: __init__
    :platform: Linux
    :synopsis: backend package definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from .base import Backend
from .base import BackendError
from .base import BackendFactory
from .local import LocalBackend
from .local import LocalBackendFactory

__all__ = [
    "Backend",
    "BackendError",
    "BackendFactory",
    "LocalBackend",
    "LocalBackendFactory",
]
