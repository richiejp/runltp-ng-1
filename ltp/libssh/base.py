"""
.. module:: base.py
    :platform: Linux
    :synopsis: libssh base module initializer

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ctypes import cdll
from ctypes.util import find_library

LIBSSH_PATH = find_library('libssh')
if not LIBSSH_PATH:
    LIBSSH_PATH = "libssh.so"

libssh = cdll.LoadLibrary(LIBSSH_PATH)
