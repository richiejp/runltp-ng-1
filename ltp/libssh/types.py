"""
.. module:: types.py
    :platform: Linux
    :synopsis: libssh types bindings

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ctypes import c_int
from ctypes import c_char_p
from ctypes import c_void_p
from ctypes import Structure
from ctypes import POINTER


class _SSHKeyStruct(Structure):
    """
    Structure to match ssh_key struct.
    """

    _fields_ = [
        ('type', c_int),
        ('flags', c_int),
        ('type_c', c_char_p),
        ('ecdsa_nid', c_int),
        ('dsa', c_void_p),
        ('rsa', c_void_p),
        ('ecdsa', c_void_p),
        ('ed25519_pubkey', c_void_p),
        ('ed25519_privkey', c_void_p),
        ('cert', c_void_p),
        ('cert_types', c_int),
    ]


# pylint: disable=invalid-name
c_ssh_session = c_void_p
c_ssh_channel = c_void_p
c_ssh_key = POINTER(_SSHKeyStruct)
