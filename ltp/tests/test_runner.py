"""
Unittest for runner package.
"""
import os
import time
import threading
import subprocess
import pytest
import signal
import unittest.mock
from ltp.runner import ShellRunner
from ltp.runner import SSHRunner
from ltp.runner import RunnerError
from ltp.runner import SerialRunner
from ltp.runner import RunnerError


TEST_SSH_PASSWORD = os.environ.get("TEST_SSH_PASSWORD", None)


class TestSSHRunner:
    """
    Test SSHRunner class implementation.
    """

    @pytest.fixture(scope="module")
    def config(self):
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

    def test_init(self, config):
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

    def test_name(self, config):
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
    def test_bad_hostname(self, config):
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
    def test_bad_port(self, config):
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
    def test_bad_user(self, config):
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
    def test_bad_key_file(self, config):
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
    def test_bad_password(self, config):
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
    def test_bad_auth(self, config):
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
    def test_connection_key_file(self, config):
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
        assert ret["exec_time"] > 0

    @pytest.mark.usefixtures("ssh_server")
    def test_stop(self, config):
        """
        Test connection using key_file and stop during a long
        command execution.
        """
        client = SSHRunner(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        def _threaded():
            time.sleep(2)
            client.stop()

        client.start()

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        ret = client.run_cmd("sleep 10", 20)

        assert ret["command"] == "sleep 10"
        assert ret["stdout"] == ""
        assert ret["returncode"] == -1
        assert ret["timeout"] == 20
        assert ret["exec_time"] > 0

    @pytest.mark.usefixtures("ssh_server")
    @pytest.mark.skipif(TEST_SSH_PASSWORD is None, reason="Empty SSH password")
    def test_connection_user_password(self, config):
        """
        Test connection using username/password.
        """
        client = SSHRunner(
            host=config.hostname,
            port=config.port,
            user=config.user,
            password=TEST_SSH_PASSWORD)

        client.start()
        ret = client.run_cmd("echo 'this is not a test'", 1)
        client.stop()

        assert ret["command"] == "echo 'this is not a test'"
        assert ret["stdout"] == "this is not a test\n"
        assert ret["returncode"] == 0
        assert ret["timeout"] == 1
        assert ret["exec_time"] > 0


class TestSerialRunner:
    """
    Test SerialRunner class.
    """

    def test_init(self, tmpdir):
        """
        Test class initialization.
        """
        target = tmpdir / "target"
        target.write("")

        with open(target, "r+") as ftarget:
            with pytest.raises(ValueError):
                SerialRunner(None, ftarget)

            with pytest.raises(ValueError):
                SerialRunner(ftarget, None)

    def test_name(self, tmpdir):
        """
        Test name property.
        """
        target = tmpdir / "target"
        target.write("")

        with open(target, "r+") as ftarget:
            assert SerialRunner(ftarget, ftarget).name == "serial"

    def test_command(self, tmpdir):
        """
        Test start() method.
        """
        target = tmpdir / "target"
        target.write("")

        with open(target, "r+") as mytarget:
            data = None

            def _emulate_shell(cmd):
                """
                Simple mock that gets command, execute it and write into target
                file. This function overrides TextIOWrapper::write method.
                """
                if not cmd:
                    raise ValueError("command is empty")

                with open(target, 'a+') as ftarget:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        shell=True)

                    stdout = proc.communicate()[0]
                    ftarget.write(stdout.decode("utf-8"))

            runner = SerialRunner(mytarget, mytarget)
            runner.start()

            runner._stdin.write = unittest.mock.MagicMock()
            runner._stdin.write.side_effect = _emulate_shell

            data = runner.run_cmd("echo 'this-is-not-a-test'", 1)
            runner.stop()

            assert data["command"] == "echo 'this-is-not-a-test'"
            assert data["timeout"] == 1
            assert data["returncode"] == 0
            assert data["stdout"] == "this-is-not-a-test\n"
            assert data["exec_time"] > 0

    def test_command_timeout(self, tmpdir):
        """
        Test start() method when goes in timeout.
        """
        target = tmpdir / "target"
        target.write("")

        with open(target, "r+") as mytarget:
            runner = SerialRunner(mytarget, mytarget)
            runner.start()

            # we are not handling the command, so we will run out of time
            with pytest.raises(RunnerError):
                runner.run_cmd("echo 'this-is-not-a-test'", 0.01)


class TestShellRunner:
    """
    Test ShellRunner class implementation.
    """

    def test_name(self):
        """
        Test name property.
        """
        assert ShellRunner().name == "shell"

    def test_start(self):
        """
        Test start method.
        """
        ShellRunner().start()

    def test_run_cmd(self):
        """
        Test run_cmd method.
        """
        ret = ShellRunner().run_cmd("test", 1)
        assert ret["command"] == "test"
        assert ret["returncode"] == 1
        assert ret["stdout"] == ""
        assert ret["timeout"] == 1
        assert ret["exec_time"] > 0

    def test_run_cmd_timeout(self):
        """
        Test run_cmd method when timeout occurs.
        """
        ret = ShellRunner().run_cmd("sleep 10", 0.1)
        assert ret["command"] == "sleep 10"
        assert ret["returncode"] == -signal.SIGKILL
        assert ret["stdout"] == ""
        assert ret["timeout"] == 0.1
        assert ret["exec_time"] > 0

    def test_run_cmd_cwd(self, tmpdir):
        """
        Test run_cmd method using cwd initialization.
        """
        tmpfile = tmpdir / "myfile"
        tmpfile.write("")

        ret = ShellRunner(cwd=str(tmpdir)).run_cmd("ls", 10)
        assert ret["command"] == "ls"
        assert ret["returncode"] == 0
        assert ret["stdout"] == "myfile\n"
        assert ret["timeout"] == 10
        assert ret["exec_time"] > 0

    def test_run_cmd_env(self):
        """
        Test run_cmd method using environment variables.
        """
        ret = ShellRunner(env=dict(HELLO="world")).run_cmd(
            "echo -n $HELLO", 10)
        assert ret["command"] == "echo -n $HELLO"
        assert ret["returncode"] == 0
        assert ret["stdout"] == "world"
        assert ret["timeout"] == 10
        assert ret["exec_time"] > 0

    def test_stop(self):
        """
        Test stop method.
        """
        shell = ShellRunner()

        class MyThread(threading.Thread):
            def __init__(self):
                super(MyThread, self).__init__()
                self.result = None
                self.daemon = True

            def run(self):
                self.result = shell.run_cmd("sleep 10", 20)

        thread = MyThread()
        thread.start()

        time.sleep(0.5)
        shell.stop()

        thread.join()
        ret = thread.result

        assert ret["command"] == "sleep 10"
        assert ret["returncode"] == -signal.SIGTERM
        assert ret["stdout"] == ""
        assert ret["timeout"] == 20
        assert ret["exec_time"] > 0

    def test_force_stop(self):
        """
        Test force_stop method.
        """
        shell = ShellRunner()

        class MyThread(threading.Thread):
            def __init__(self):
                super(MyThread, self).__init__()
                self.result = None
                self.daemon = True

            def run(self):
                self.result = shell.run_cmd("sleep 10", 20)

        thread = MyThread()
        thread.start()

        time.sleep(0.5)
        shell.force_stop()

        thread.join()
        ret = thread.result

        assert ret["command"] == "sleep 10"
        assert ret["returncode"] == -signal.SIGKILL
        assert ret["stdout"] == ""
        assert ret["timeout"] == 20
        assert ret["exec_time"] > 0
