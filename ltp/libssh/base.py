"""
.. module:: base.py
    :platform: Linux
    :synopsis: libssh base module initializer

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ctypes import cdll
from ctypes.util import find_library

LIBSSH_PATH = find_library('ssh')
libssh = cdll.LoadLibrary(LIBSSH_PATH)
