"""
.. module:: __init__
    :platform: Linux
    :synopsis: metadata package initializer

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from .base import Metadata
from .base import MetadataError
from .runtest import RuntestMetadata

__all__ = [
    "Metadata",
    "MetadataError",
    "RuntestMetadata",
]
