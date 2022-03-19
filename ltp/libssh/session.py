"""
.. module:: ssh.py
    :platform: Linux
    :synopsis: libssh session bindings

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ctypes import c_int
from ctypes import c_void_p
from ctypes import c_char_p
from ctypes import POINTER
from ltp.libssh.base import libssh
from ltp.libssh.types import c_ssh_session, c_ssh_key

# ssh_session ssh_new(void)
ssh_new = libssh.ssh_new
ssh_new.argtypes = []
ssh_new.restype = c_ssh_session

# void ssh_free(ssh_session session)
ssh_free = libssh.ssh_free
ssh_free.argtypes = [c_ssh_session]
ssh_free.restype = None

# int ssh_connect(ssh_session session)
ssh_connect = libssh.ssh_connect
ssh_connect.argtypes = [c_ssh_session]
ssh_connect.restype = c_int

# void ssh_disconnect(ssh_session session)
ssh_disconnect = libssh.ssh_disconnect
ssh_disconnect.argtypes = [c_ssh_session]
ssh_disconnect.restype = None

# int ssh_init(void)
ssh_init = libssh.ssh_init
ssh_init.argtypes = []
ssh_init.restype = c_int

# int ssh_finalize(void)
ssh_finalize = libssh.ssh_finalize
ssh_finalize.argtypes = []
ssh_finalize.restype = c_int

# int ssh_get_error_code(void *error)
ssh_get_error_code = libssh.ssh_get_error_code
ssh_get_error_code.argtypes = [c_ssh_session]
ssh_get_error_code.restype = c_int

# const char* ssh_get_error(void* error)
ssh_get_error = libssh.ssh_get_error
ssh_get_error.argtypes = [c_ssh_session]
ssh_get_error.restype = c_char_p

# int ssh_get_status(ssh_session session)
ssh_get_status = libssh.ssh_get_status
ssh_get_status.argtypes = [c_ssh_session]
ssh_get_status.restype = c_int

# int ssh_options_set(
#   ssh_session session,
#   enum ssh_options_e type,
#   const void *value)
ssh_options_set = libssh.ssh_options_set
ssh_options_set.argtypes = [c_ssh_session, c_int, c_void_p]
ssh_options_set.restype = c_int

# int ssh_userauth_none(ssh_session session, const char *username)
ssh_userauth_none = libssh.ssh_userauth_none
ssh_userauth_none.argtypes = [c_ssh_session, c_char_p]
ssh_userauth_none.restype = c_int

# int ssh_userauth_password(
#   ssh_session session,
#   const char *username,
#   const char *password)
ssh_userauth_password = libssh.ssh_userauth_password
ssh_userauth_password.argtypes = [c_ssh_session, c_char_p, c_char_p]
ssh_userauth_password.restype = c_int

# int ssh_userauth_publickey(
#   ssh_session session,
#   const char *username,
#   const ssh_key privkey)
ssh_userauth_publickey = libssh.ssh_userauth_publickey
ssh_userauth_publickey.argtypes = [c_ssh_session, c_char_p, c_ssh_key]
ssh_userauth_publickey.restype = c_int

# int ssh_userauth_publickey(
#   ssh_session session,
#   const char *username,
#   const char *passphrase)
ssh_userauth_publickey_auto = libssh.ssh_userauth_publickey_auto
ssh_userauth_publickey_auto.argtypes = [c_ssh_session, c_char_p, c_char_p]
ssh_userauth_publickey_auto.restype = c_int

# ssh_key ssh_key_new(void)
ssh_key_new = libssh.ssh_key_new
ssh_key_new.argtypes = []
ssh_key_new.restype = c_ssh_key

# void ssh_key_free(ssh_key key)
ssh_key_free = libssh.ssh_key_free
ssh_key_free.argtypes = [c_ssh_key]
ssh_key_free.restype = None

# int ssh_pki_import_privkey_file(
#   const char *filename,
#   const char *passphrase,
#   ssh_auth_callback auth_fn,
#   void *auth_data,
#   ssh_key *pkey)
ssh_pki_import_privkey_file = libssh.ssh_pki_import_privkey_file
ssh_pki_import_privkey_file.argtypes = [
    c_char_p,
    c_char_p,
    c_void_p,
    c_void_p,
    POINTER(c_ssh_key)]
ssh_pki_import_privkey_file.restype = c_int

# int ssh_get_openssh_version(ssh_session session)
ssh_get_openssh_version = libssh.ssh_get_openssh_version
ssh_get_openssh_version.argtypes = [c_ssh_session]
ssh_get_openssh_version.restype = c_int

# int ssh_get_version(ssh_session session)
ssh_get_version = libssh.ssh_get_version
ssh_get_version.argtypes = [c_ssh_session]
ssh_get_version.restype = c_int

# int ssh_get_status(ssh_session session)
ssh_get_status = libssh.ssh_get_status
ssh_get_status.argtypes = [c_ssh_session]
ssh_get_status.restype = c_int
