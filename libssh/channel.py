"""
.. module:: channel.py
    :platform: Linux
    :synopsis: libssh channel bindings

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ctypes import c_int
from ctypes import c_void_p
from ctypes import c_uint32
from ctypes import c_char_p
from libssh.base import libssh
from libssh.types import c_ssh_session, c_ssh_channel


# ssh_channel ssh_channel_new(ssh_session session)
ssh_channel_new = libssh.ssh_channel_new
ssh_channel_new.argtypes = [c_ssh_session]
ssh_channel_new.restype = c_ssh_channel

# int ssh_channel_send_eof(ssh_channel channel)
ssh_channel_send_eof = libssh.ssh_channel_send_eof
ssh_channel_send_eof.argtypes = [c_ssh_channel]
ssh_channel_send_eof.restype = c_int

# void ssh_channel_close(ssh_channel channel)
ssh_channel_close = libssh.ssh_channel_close
ssh_channel_close.argtypes = [c_ssh_channel]
ssh_channel_close.restype = None

# void ssh_channel_free(ssh_channel channel)
ssh_channel_free = libssh.ssh_channel_free
ssh_channel_free.argtypes = [c_ssh_channel]
ssh_channel_free.restype = None

# LIBSSH_API int ssh_channel_open_session(ssh_channel channel)
ssh_channel_open_session = libssh.ssh_channel_open_session
ssh_channel_open_session.argtypes = [c_ssh_channel]
ssh_channel_open_session.restype = c_int

# int ssh_channel_read_timeout(
#   ssh_channel channel,
#   void *dest,
#   uint32_t count,
#   int is_stderr,
#   int timeout_ms)
ssh_channel_read_timeout = libssh.ssh_channel_read_timeout
ssh_channel_read_timeout.argtypes = [c_ssh_channel, c_void_p, c_uint32, c_int]
ssh_channel_read_timeout.restype = c_int

# int ssh_channel_request_exec(ssh_channel channel, const char *cmd)
ssh_channel_request_exec = libssh.ssh_channel_request_exec
ssh_channel_request_exec.argtypes = [c_ssh_channel, c_char_p]
ssh_channel_request_exec.restype = c_int

# int ssh_channel_get_exit_status(ssh_channel channel)
ssh_channel_get_exit_status = libssh.ssh_channel_get_exit_status
ssh_channel_get_exit_status.argtypes = [c_ssh_channel]
ssh_channel_get_exit_status.restype = c_int
