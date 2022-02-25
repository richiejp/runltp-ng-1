"""
Unittest for ssh module.
"""
import os
import time
import socket
import logging
import threading
import pytest
import paramiko
from ltp.ssh import SSHBackend
from ltp.backend import BackendError


KEY = b'\x0c\xe2\x57\xb3\x23\x4c\x57\x22\x54\xba\x56\x79\x62\x5c\x95\x37'


class ServerKeyOnly(paramiko.ServerInterface):
    """
    SSH server for publickey only.
    """

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def get_allowed_auths(self, username):
        return "publickey"

    def check_auth_publickey(self, username, key):
        if key.get_name() == 'ssh-rsa' and key.get_fingerprint() == KEY:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_exec_request(self, channel, command):
        if command != b"yes":
            return False
        return True


class ServerPasswordOnly(paramiko.ServerInterface):
    """
    Simple SSH server for testing.
    """

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def get_allowed_auths(self, username):
        return "password"

    def check_auth_publickey(self, username, key):
        # force password only login
        return paramiko.AUTH_FAILED

    def check_auth_password(self, username, password):
        if username == 'root' and password == 'toor':
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED


@pytest.fixture
def run_server(request):
    """
    Setup/Teardown for unittests.
    """
    password_only = request.node.get_closest_marker("ssh_password_only")

    class MyThread(threading.Thread):
        """
        Handle SSH connection.
        """

        def __init__(self):
            threading.Thread.__init__(self)
            self.daemon = True
            self.transport = None
            self.socket = None

        def run(self):
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(("localhost", 2222))
            self.socket.listen(100)

            socks, _ = self.socket.accept()

            self.transport = paramiko.Transport(socks)
            self.transport.set_gss_host(socket.getfqdn(""))
            self.transport.load_server_moduli()

            tests_dir = os.path.dirname(os.path.realpath(__file__))
            host_key = paramiko.RSAKey(
                filename=os.path.join(tests_dir, "id_rsa"))
            self.transport.add_server_key(host_key)

            server = None
            if password_only:
                server = ServerPasswordOnly()
            else:
                server = ServerKeyOnly()

            self.transport.start_server(server=server)

    thread = MyThread()
    thread.start()

    yield

    if thread.transport:
        thread.transport.close()

    thread.socket.shutdown(socket.SHUT_RDWR)
    thread.socket.close()
    thread.join()


def test_name():
    """
    Test if name property returns the right name
    """
    client = SSHBackend(host="localhost", port=2222)
    assert client.name == "ssh"


@pytest.mark.usefixtures("run_server")
def test_connection_force_stop(caplog):
    """
    Test connection stopping it using force_stop.
    """
    caplog.set_level(logging.INFO, logger="paramiko.transport:transport.py")

    tests_dir = os.path.dirname(os.path.realpath(__file__))
    keyfile = os.path.join(tests_dir, "id_rsa.pub")

    client = SSHBackend(
        host="localhost",
        port=2222,
        user=None,
        key_file=keyfile)

    thread = threading.Thread(target=lambda: client.start(), daemon=True)
    thread.start()
    time.sleep(1)
    client.force_stop()

    assert "Connection closed" in caplog.messages


@pytest.mark.usefixtures("run_server")
def test_connection_key_file(caplog):
    """
    Test connection using key_file.
    """
    caplog.set_level(logging.INFO, logger="paramiko.transport:transport.py")

    tests_dir = os.path.dirname(os.path.realpath(__file__))
    keyfile = os.path.join(tests_dir, "id_rsa.pub")

    client = SSHBackend(
        host="localhost",
        port=2222,
        user=None,
        key_file=keyfile)

    client.start()
    client.stop()

    assert "Authentication (publickey) successful!" in caplog.messages


@pytest.mark.usefixtures("run_server")
@pytest.mark.ssh_password_only
def test_connection_user_password(caplog):
    """
    Test connection using username/password.
    """
    caplog.set_level(logging.INFO, logger="paramiko.transport:transport.py")

    client = SSHBackend(
        host="localhost",
        port=2222,
        user="root",
        password="toor")

    client.start()
    client.stop()

    assert "Authentication (password) successful!" in caplog.messages


@pytest.mark.usefixtures("run_server")
@pytest.mark.ssh_password_only
def test_connection_wrong_user(caplog):
    """
    Test connection using a wrong username.
    """
    client = SSHBackend(
        host="localhost",
        port=2222,
        user="myuser",
        password="toor")

    with pytest.raises(BackendError):
        client.start()

    assert "Authentication (password) failed." in caplog.messages


@pytest.mark.usefixtures("run_server")
def test_run_cmd(mocker):
    """
    Test run_cmd method.
    """
    # it's almost impossible to test run_cmd without mocking exec_command,
    # since we need the channel object to send data from server to client
    def my_exec_command(*args, **kwargs):
        stdout = mocker.MagicMock()
        stdout.readlines.return_value = ["yes\n"]
        stdout.channel.recv_exit_status.return_value = 0
        return None, stdout, None

    mocker.patch.object(paramiko.SSHClient, 'exec_command', my_exec_command)

    client = SSHBackend(host="localhost", port=2222)
    client.start()
    ret = client.run_cmd("yes", 1)
    client.stop()

    assert ret["command"] == "yes"
    assert ret["timeout"] == 1
    assert ret["stdout"] == "yes\n"
    assert ret["returncode"] == 0


@pytest.mark.usefixtures("run_server")
def test_run_cmd_error(mocker):
    """
    Test run_cmd method raises paramiko.SSHException exception.
    """
    def my_exec_command(*args, **kwargs):
        raise paramiko.SSHException("test exception")

    mocker.patch.object(paramiko.SSHClient, 'exec_command', my_exec_command)

    client = SSHBackend(host="localhost", port=2222)
    client.start()

    with pytest.raises(BackendError):
        client.run_cmd("yes", 1)


@pytest.mark.usefixtures("run_server")
def test_run_cmd_file_not_found_error(mocker):
    """
    Test run_cmd method raises FileNotFoundError exception.
    """
    def my_exec_command(*args, **kwargs):
        raise FileNotFoundError("test exception")

    mocker.patch.object(paramiko.SSHClient, 'exec_command', my_exec_command)

    client = SSHBackend(host="localhost", port=2222)
    client.start()

    with pytest.raises(BackendError):
        client.run_cmd("yes", 1)
