"""
Unittest for ssh module.
"""
import os
import time
import socket
import threading
import subprocess
import logging
import pytest
from ltp.runner import SSHRunner
from ltp.runner import RunnerError


class OpenSSHServer:
    """
    Class helper used to initialize a OpenSSH server.
    """

    def __init__(self, tmpdir: str, port: int = 2222) -> None:
        """
        :param port: ssh server port
        :type port: int
        """
        self._logger = logging.getLogger("sshserver")

        self._dir_name = os.path.dirname(__file__)
        self._server_key = os.path.abspath(
            os.path.sep.join([self._dir_name, 'id_rsa']))
        self._sshd_config_tmpl = os.path.abspath(
            os.path.sep.join([self._dir_name, 'sshd_config.tmpl']))
        self._sshd_config = os.path.abspath(
            os.path.sep.join([tmpdir, 'sshd_config']))

        self._port = port
        self._proc = None
        self._thread = None
        self._stop_thread = False

        # setup permissions on server key
        os.chmod(self._server_key, 0o600)

        # create sshd configuration file
        self._create_sshd_config()

    def _wait_for_port(self) -> None:
        """
        Wait until server is up.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while sock.connect_ex(('127.0.0.1', self._port)) != 0:
            time.sleep(.1)
        del sock

    def _create_sshd_config(self) -> None:
        """
        Create SSHD configuration file from template config expanding
        authorized_keys.
        """
        self._logger.info("creating SSHD configuration")

        # read template sshd configuration file
        with open(self._sshd_config_tmpl, 'r') as fh:
            tmpl = fh.read()

        # replace parent directory with the current directory
        auth_file = os.path.join(os.path.abspath(
            self._dir_name), 'authorized_keys')
        tmpl = tmpl.replace('{{authorized_keys}}', auth_file)

        self._logger.info("SSHD configuration is: %s", tmpl)

        # write sshd configuration file
        with open(self._sshd_config, 'w') as fh:
            for line in tmpl:
                fh.write(line)
            fh.write(os.linesep)

        self._logger.info(
            "'%s' configuration file has been created", self._sshd_config)

    def start(self) -> None:
        """
        Start ssh server.
        """
        cmd = [
            '/usr/sbin/sshd',
            '-ddd',
            '-D',
            '-p', str(self._port),
            '-h', self._server_key,
            '-f', self._sshd_config,
        ]

        self._logger.info("starting SSHD with command: %s", cmd)

        def run_server():
            self._proc = subprocess.Popen(
                " ".join(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                universal_newlines=True,
            )

            while self._proc.poll() is None:
                if self._stop_thread:
                    break

                line = self._proc.stdout.readline()
                if not line:
                    break

                self._logger.info(line.rstrip())

        self._thread = threading.Thread(target=run_server)
        self._thread.start()

        time.sleep(2)

        self._logger.info("service is up to use")

    def stop(self) -> None:
        """
        Stop ssh server.
        """
        if not self._proc or not self._thread:
            return

        self._logger.info("stopping SSHD service")

        self._proc.kill()
        self._stop_thread = True
        self._thread.join(timeout=10)

        self._logger.info("service stopped")


@pytest.fixture(scope="module")
def config():
    """
    Fixture exposing configuration
    """
    class Config:
        """
        Configuration class
        """
        import pwd
        hostname = "127.0.0.1"
        port = 2222
        testsdir = os.path.abspath(os.path.dirname(__file__))
        currdir = os.path.abspath('.')
        user = pwd.getpwuid(os.geteuid()).pw_name
        user_key = os.path.sep.join([testsdir, 'id_rsa'])
        user_key_pub = os.path.sep.join([testsdir, 'id_rsa.pub'])

    return Config()


@pytest.fixture
def ssh_server(tmpdir):
    server = OpenSSHServer(str(tmpdir), port=2222)
    server.start()
    yield
    server.stop()


def test_init(config):
    """
    Test class initializer.
    """
    with pytest.raises(ValueError):
        SSHRunner(
            host=None,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

    with pytest.raises(ValueError):
        SSHRunner(
            host=config.hostname,
            port=-100,
            user=config.user,
            key_file=config.user_key)

    with pytest.raises(ValueError):
        SSHRunner(
            host=config.hostname,
            port=config.port,
            user=None,
            key_file=config.user_key)

    with pytest.raises(ValueError):
        SSHRunner(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file="this_key_doesnt_exist.key")


def test_name(config):
    """
    Test if name property returns the right name
    """
    client = SSHRunner(
        host="127.0.0.2",
        port=config.port,
        user=config.user,
        key_file=config.user_key)
    assert client.name == "ssh"


@pytest.mark.usefixtures("ssh_server")
def test_bad_hostname(config):
    """
    Test connection when a bad hostname is given.
    """
    client = SSHRunner(
        host="127.0.0.2",
        port=config.port,
        user=config.user,
        key_file=config.user_key)

    with pytest.raises(RunnerError):
        client.start()


@pytest.mark.usefixtures("ssh_server")
def test_bad_port(config):
    """
    Test connection when a bad port is given.
    """
    client = SSHRunner(
        host=config.hostname,
        port=12345,
        user=config.user,
        key_file=config.user_key)

    with pytest.raises(RunnerError):
        client.start()


@pytest.mark.usefixtures("ssh_server")
def test_bad_user(config):
    """
    Test connection when a bad user is given.
    """
    client = SSHRunner(
        host=config.hostname,
        port=config.port,
        user="this_user_doesnt_exist",
        key_file=config.user_key)

    with pytest.raises(RunnerError):
        client.start()


@pytest.mark.usefixtures("ssh_server")
def test_bad_key_file(config):
    """
    Test connection when a bad key file is given.
    """
    testsdir = os.path.abspath(os.path.dirname(__file__))
    user_key_pub = os.path.sep.join([testsdir, 'id_rsa_bad'])

    with pytest.raises(RunnerError):
        client = SSHRunner(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=user_key_pub)
        client.start()


@pytest.mark.usefixtures("ssh_server")
def test_bad_password(config):
    """
    Test connection when a bad password is given.
    """
    client = SSHRunner(
        host=config.hostname,
        port=config.port,
        user=config.user,
        password="wrong_password")

    with pytest.raises(RunnerError):
        client.start()


@pytest.mark.usefixtures("ssh_server")
def test_bad_auth(config):
    """
    Test a unsupported authentication method.
    """
    client = SSHRunner(
        host=config.hostname,
        port=config.port,
        user=config.user)

    with pytest.raises(RunnerError):
        client.start()


@pytest.mark.usefixtures("ssh_server")
def test_connection_key_file(config):
    """
    Test connection using key_file.
    """
    client = SSHRunner(
        host=config.hostname,
        port=config.port,
        user=config.user,
        key_file=config.user_key)

    client.start()
    ret = client.run_cmd("echo 'this is not a test'", 1)
    client.stop()

    assert ret["command"] == "echo 'this is not a test'"
    assert ret["stdout"] == "this is not a test\n"
    assert ret["returncode"] == 0
    assert ret["timeout"] == 1


@pytest.mark.usefixtures("ssh_server")
def test_connection_user_password(config):
    """
    Test connection using username/password.
    """
    client = SSHRunner(
        host=config.hostname,
        port=config.port,
        user=config.user,
        password=os.environ.get("TEST_SSH_PASSWORD", None))

    client.start()
    ret = client.run_cmd("echo 'this is not a test'", 1)
    client.stop()

    assert ret["command"] == "echo 'this is not a test'"
    assert ret["stdout"] == "this is not a test\n"
    assert ret["returncode"] == 0
    assert ret["timeout"] == 1
