"""
.. module:: __init__
    :platform: Linux
    :synopsis: results package definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from .base import SuiteResults
from .base import TestResults
from .base import Exporter
from .base import ExporterError
from .json import JSONExporter

__all__ = [
    "SuiteResults",
    "TestResults",
    "Exporter",
    "ExporterError",
    "JSONExporter",
]
