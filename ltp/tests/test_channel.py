"""
Unit tests for Channel implementations.
"""
import os
import time
import signal
from unittest import mock
import threading
import subprocess
import pytest
from ltp.channel import SSHChannel
from ltp.channel import ChannelError
from ltp.channel import ShellChannel
from ltp.channel import SerialChannel
from ltp.channel import ChannelTimeoutError

TEST_SSH_PASSWORD = os.environ.get("TEST_SSH_PASSWORD", None)


class _TestDataTransfer:
    """
    Generic tests for various data transfer implementations.
    """

    @pytest.fixture
    def transfer_client(self):
        """
        Implement this fixture to test data transfer.
        """
        pass

    def test_fetch_file_bad_args(self, tmpdir, transfer_client):
        """
        Test fetch_file method with bad arguments.
        """
        with pytest.raises(ValueError):
            transfer_client.fetch_file(None, "local_file")

        target_path = tmpdir / "target_file"
        target_path.write("runltp-ng tests")
        with pytest.raises(ValueError):
            transfer_client.fetch_file(str(target_path), None)

        with pytest.raises(ValueError):
            transfer_client.fetch_file("this_file_doesnt_exist", None)

    def test_fetch_file(self, tmpdir, transfer_client):
        """
        Test fetch_file method.
        """
        transfer_client.start()
        try:
            for i in range(0, 5):
                local_path = tmpdir / f"local_file{i}"
                target_path = tmpdir / f"target_file{i}"
                target_path.write("runltp-ng tests")

                target = str(target_path)
                local = str(local_path)

                transfer_client.fetch_file(target, local)

                assert os.path.isfile(local)
                assert open(target, 'r').read() == "runltp-ng tests"
        finally:
            transfer_client.stop()

    def test_stop_fetch_file(self, tmpdir, transfer_client):
        """
        Test stop method when running fetch_file.
        """
        local_path = tmpdir / "local_file"
        target_path = tmpdir / "target_file"

        target = str(target_path)
        local = str(local_path)

        # create a big file to have enough IO traffic and slow
        # down fetch_file() method
        with open(target, 'wb') as ftarget:
            ftarget.seek(1*1024*1024*1024-1)
            ftarget.write(b'\0')

        def _threaded():
            transfer_client.start()
            transfer_client.fetch_file(target, local)

        thread = threading.Thread(target=_threaded)
        thread.start()

        start_t = time.time()
        while not transfer_client.is_running:
            time.sleep(0.05)
            assert time.time() - start_t < 10

        # wait for local file creation before stop
        start_t = time.time()
        while not os.path.isfile(local_path):
            time.sleep(0.05)
            assert time.time() - start_t < 60

        transfer_client.stop()
        thread.join()

        target_size = os.stat(target).st_size
        local_size = os.stat(local).st_size

        assert target_size != local_size

    def test_fetch_file_timeout(self, tmpdir, transfer_client):
        """
        Test stop method when running fetch_file.
        """
        local_path = tmpdir / "local_file"
        target_path = tmpdir / "target_file"

        target = str(target_path)
        local = str(local_path)

        # create a big file to have enough IO traffic and slow
        # down fetch_file() method
        with open(target, 'wb') as ftarget:
            ftarget.seek(1*1024*1024*1024-1)
            ftarget.write(b'\0')

        with pytest.raises(ChannelTimeoutError):
            transfer_client.start()
            transfer_client.fetch_file(target, local, timeout=1)


@pytest.mark.usefixtures("ssh_server")
@pytest.mark.ssh
class TestSSHChannel(_TestDataTransfer):
    """
    Tests for SSHChannel implementation.
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

    @pytest.fixture
    def transfer_client(self, config):
        yield SSHChannel(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key
        )

    def test_init(self, config):
        """
        Test class initializer.
        """
        with pytest.raises(ValueError):
            SSHChannel(
                host=None,
                port=config.port,
                user=config.user,
                key_file=config.user_key)

        with pytest.raises(ValueError):
            SSHChannel(
                host=config.hostname,
                port=-100,
                user=config.user,
                key_file=config.user_key)

        with pytest.raises(ValueError):
            SSHChannel(
                host=config.hostname,
                port=config.port,
                user=None,
                key_file=config.user_key)

        with pytest.raises(ValueError):
            SSHChannel(
                host=config.hostname,
                port=config.port,
                user=config.user,
                key_file="this_key_doesnt_exist.key")

    def test_bad_hostname(self, config):
        """
        Test connection when a bad hostname is given.
        """
        client = SSHChannel(
            host="127.0.0.2",
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        with pytest.raises(ChannelError):
            client.start()

        client.stop()

    def test_bad_port(self, config):
        """
        Test connection when a bad port is given.
        """
        client = SSHChannel(
            host=config.hostname,
            port=12345,
            user=config.user,
            key_file=config.user_key)

        with pytest.raises(ChannelError):
            client.start()

        client.stop()

    def test_bad_user(self, config):
        """
        Test connection when a bad user is given.
        """
        client = SSHChannel(
            host=config.hostname,
            port=config.port,
            user="this_user_doesnt_exist",
            key_file=config.user_key)

        with pytest.raises(ChannelError):
            client.start()

        client.stop()

    def test_bad_key_file(self, config):
        """
        Test connection when a bad key file is given.
        """
        testsdir = os.path.abspath(os.path.dirname(__file__))
        user_key_pub = os.path.sep.join([testsdir, 'id_rsa_bad'])

        with pytest.raises(ChannelError):
            client = SSHChannel(
                host=config.hostname,
                port=config.port,
                user=config.user,
                key_file=user_key_pub)
            client.start()

        client.stop()

    def test_bad_password(self, config):
        """
        Test connection when a bad password is given.
        """
        client = SSHChannel(
            host=config.hostname,
            port=config.port,
            user=config.user,
            password="wrong_password")

        with pytest.raises(ChannelError):
            client.start()

        client.stop()

    def test_bad_auth(self, config):
        """
        Test a unsupported authentication method.
        """
        client = SSHChannel(
            host=config.hostname,
            port=config.port,
            user=config.user)

        with pytest.raises(ChannelError):
            client.start()

    def test_is_running(self, config):
        """
        Test is_running property.
        """
        client = SSHChannel(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        client.start()

        def _threaded():
            start_t = time.time()
            while not client.is_running:
                time.sleep(0.05)
                assert time.time() - start_t < 5

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        client.run_cmd("sleep 0.5")

        thread.join()
        time.sleep(0.6)
        client.stop()

    def test_connection_key_file(self, tmpdir, config):
        """
        Test connection using key_file.
        """
        client = SSHChannel(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        client.start()

        env = {"MYVAR": "hello"}
        cwd = str(tmpdir)

        data = client.run_cmd(
            "echo $PWD-$MYVAR",
            timeout=1,
            env=env,
            cwd=cwd)
        client.stop()

        assert data["command"] == "echo $PWD-$MYVAR"
        assert data["timeout"] == 1
        assert data["returncode"] == 0
        assert data["stdout"] == f"{str(tmpdir)}-hello\n"
        assert data["exec_time"] > 0
        assert data["env"] == env
        assert data["cwd"] == cwd

    def test_stop_run_cmd(self, config):
        """
        Test connection using key_file and stop during a long
        command execution.
        """
        client = SSHChannel(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        def _threaded():
            client.start()
            data = client.run_cmd("sleep 4")

            assert data["command"] == "sleep 4"
            assert data["returncode"] == -1
            assert data["stdout"] == ""
            assert data["exec_time"] > 0

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        start_t = time.time()
        while not client.is_running:
            time.sleep(0.05)
            assert time.time() - start_t < 5

        client.stop()
        thread.join()

    def test_run_cmd_timeout(self, config):
        """
        Test run_cmd when going in timeout.
        """
        client = SSHChannel(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        client.start()

        with pytest.raises(ChannelTimeoutError):
            client.run_cmd("sleep 4", timeout=1)

    @pytest.mark.skipif(TEST_SSH_PASSWORD is None, reason="Empty SSH password")
    def test_connection_user_password(self, tmpdir, config):
        """
        Test connection using username/password.
        """
        client = SSHChannel(
            host=config.hostname,
            port=config.port,
            user=config.user,
            password=TEST_SSH_PASSWORD)

        env = {"MYVAR": "hello"}
        cwd = str(tmpdir)

        client.start()

        data = client.run_cmd(
            "echo $PWD-$MYVAR",
            timeout=1,
            env=env,
            cwd=cwd)
        client.stop()

        assert data["command"] == "echo $PWD-$MYVAR"
        assert data["timeout"] == 1
        assert data["returncode"] == 0
        assert data["stdout"] == f"{str(tmpdir)}-hello\n"
        assert data["exec_time"] > 0
        assert data["env"] == env
        assert data["cwd"] == cwd


class TestShellChannel(_TestDataTransfer):
    """
    Test ShellChannel class implementation.
    """

    @pytest.fixture
    def transfer_client(self):
        yield ShellChannel()

    def test_start(self):
        """
        Test start method.
        """
        ShellChannel().start()

    def test_run_cmd(self):
        """
        Test run_cmd method.
        """
        ret = ShellChannel().run_cmd("test", timeout=1)
        assert ret["command"] == "test"
        assert ret["returncode"] == 1
        assert ret["stdout"] == ""
        assert ret["timeout"] == 1
        assert ret["exec_time"] > 0
        assert ret["cwd"] is None
        assert ret["env"] is None

    def test_run_cmd_timeout(self):
        """
        Test run_cmd method when timeout occurs.
        """
        channel = ShellChannel()
        with pytest.raises(ChannelTimeoutError):
            channel.run_cmd("sleep 10", timeout=0.1)

    def test_run_cmd_cwd(self, tmpdir):
        """
        Test run_cmd method using cwd initialization.
        """
        tmpfile = tmpdir / "myfile"
        tmpfile.write("")

        ret = ShellChannel().run_cmd("ls", timeout=10, cwd=str(tmpdir))
        assert ret["command"] == "ls"
        assert ret["returncode"] == 0
        assert ret["stdout"] == "myfile\n"
        assert ret["timeout"] == 10
        assert ret["exec_time"] > 0
        assert ret["cwd"] == str(tmpdir)
        assert ret["env"] is None

    def test_run_cmd_env(self):
        """
        Test run_cmd method using environment variables.
        """
        env = dict(HELLO="world")
        ret = ShellChannel().run_cmd(
            "echo -n $HELLO",
            timeout=10,
            env=env)
        assert ret["command"] == "echo -n $HELLO"
        assert ret["returncode"] == 0
        assert ret["stdout"] == "world"
        assert ret["timeout"] == 10
        assert ret["exec_time"] > 0
        assert ret["cwd"] is None
        assert ret["env"] == env

    def test_stop_run_cmd(self):
        """
        Test stop method.
        """
        shell = ShellChannel()

        class MyThread(threading.Thread):
            def __init__(self):
                super(MyThread, self).__init__()
                self.result = None
                self.daemon = True

            def run(self):
                self.result = shell.run_cmd("sleep 10", timeout=20)

        thread = MyThread()
        thread.start()

        start_t = time.time()
        while not shell.is_running:
            time.sleep(0.01)
            assert time.time() - start_t < 10

        shell.stop()

        thread.join()
        ret = thread.result

        assert ret["command"] == "sleep 10"
        assert ret["returncode"] == -signal.SIGTERM
        assert ret["stdout"] == ""
        assert ret["timeout"] == 20
        assert ret["exec_time"] > 0
        assert ret["cwd"] is None
        assert ret["env"] is None

    def test_force_stop(self):
        """
        Test force_stop method.
        """
        shell = ShellChannel()

        class MyThread(threading.Thread):
            def __init__(self):
                super(MyThread, self).__init__()
                self.result = None
                self.daemon = True

            def run(self):
                self.result = shell.run_cmd("sleep 10", 20)

        thread = MyThread()
        thread.start()

        start_t = time.time()
        while not shell.is_running:
            time.sleep(0.01)
            assert time.time() - start_t < 10

        shell.force_stop()

        thread.join()
        ret = thread.result

        assert ret["command"] == "sleep 10"
        assert ret["returncode"] == -signal.SIGKILL
        assert ret["stdout"] == ""
        assert ret["timeout"] == 20
        assert ret["exec_time"] > 0
        assert ret["cwd"] is None
        assert ret["env"] is None


@pytest.mark.xfail
class TestSerialChannel(_TestDataTransfer):
    """
    Test SerialChannel class.
    """

    @pytest.fixture
    def transfer_client(self, tmpdir):
        transport_dev = tmpdir / "ttyS0"
        transport_dev.write("")

        transport_path = tmpdir / "transport.bin"
        transport_path.write("")

        target = tmpdir / "target"
        target.write("")

        env = {"MYVAR": "hello"}
        cwd = str(tmpdir)

        mytarget = open(target, "r+")

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
                    shell=True,
                    env=env,
                    cwd=cwd)

                stdout = proc.communicate()[0]
                ftarget.write(stdout.decode("utf-8"))

        runner = SerialChannel(
            stdin=mytarget,
            stdout=mytarget,
            transport_dev=str(transport_dev),
            transport_path=str(transport_path))
        runner.start()

        runner._stdin.write = mock.MagicMock()
        runner._stdin.write.side_effect = _emulate_shell

        yield runner

        mytarget.close()

    def test_init(self, tmpdir):
        """
        Test class initialization.
        """
        target = tmpdir / "target"
        target.write("")

        with open(target, "r+") as ftarget:
            with pytest.raises(ValueError):
                SerialChannel(stdin=None,
                              stdout=ftarget,
                              transport_dev=ftarget,
                              transport_path=ftarget)

            with pytest.raises(ValueError):
                SerialChannel(stdin=ftarget,
                              stdout=None,
                              transport_dev=str(target),
                              transport_path=str(target))

            with pytest.raises(ValueError):
                SerialChannel(stdin=ftarget,
                              stdout=ftarget,
                              transport_dev=None,
                              transport_path=str(target))

            with pytest.raises(ValueError):
                SerialChannel(stdin=ftarget,
                              stdout=ftarget,
                              transport_dev=None,
                              transport_path=str(target))

            with pytest.raises(ValueError):
                SerialChannel(stdin=ftarget,
                              stdout=ftarget,
                              transport_path=str(target),
                              transport_dev=None)

    def test_run_cmd(self, tmpdir):
        """
        Test run_cmd method.
        """
        transport_path = tmpdir / "transport.bin"
        transport_path.write("")

        transport_dev = os.path.join(str(tmpdir), "ttyS0")
        os.symlink(str(transport_path), transport_dev)

        target = tmpdir / "target"
        target.write("")

        env = {"MYVAR": "hello"}
        cwd = str(tmpdir)

        with open(target, "r+") as mytarget:
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
                        shell=True,
                        env=env,
                        cwd=cwd)

                    stdout = proc.communicate()[0]
                    ftarget.write(stdout.decode("utf-8"))

            runner = SerialChannel(
                stdin=mytarget,
                stdout=mytarget,
                transport_dev=str(transport_dev),
                transport_path=str(transport_path))

            runner.start()

            runner._stdin.write = mock.MagicMock()
            runner._stdin.write.side_effect = _emulate_shell

            data = runner.run_cmd(
                "echo $PWD-$MYVAR",
                timeout=1,
                env=env,
                cwd=cwd)
            runner.stop()

            assert data["command"] == "echo $PWD-$MYVAR"
            assert data["timeout"] == 1
            assert data["returncode"] == 0
            assert data["stdout"] == f"{str(tmpdir)}-hello\n"
            assert data["exec_time"] > 0
            assert data["env"] == env
            assert data["cwd"] == cwd

    def test_run_cmd_timeout(self, tmpdir):
        """
        Test run_cmd method when goes in timeout.
        """
        transport_dev = tmpdir / "ttyS0"
        transport_dev.write("")

        transport_path = tmpdir / "transport.bin"
        transport_path.write("")

        target = tmpdir / "target"
        target.write("")

        with open(target, "r+") as mytarget:
            runner = SerialChannel(
                stdin=mytarget,
                stdout=mytarget,
                transport_dev=str(transport_dev),
                transport_path=str(transport_path))
            runner.start()

            with pytest.raises(ChannelTimeoutError):
                runner.run_cmd("sleep 1", timeout=0.5)

    def test_stop_run_cmd(self, tmpdir, transfer_client):
        """
        Test run_cmd method when it's stopped.
        """
        def _threaded():
            start_t = time.time()
            while not transfer_client.is_running:
                assert time.time() - start_t < 4

            transfer_client.stop()

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        env = {"MYVAR": "hello"}
        cwd = str(tmpdir)

        data = transfer_client.run_cmd(
            "sleep 2",
            timeout=4,
            env=env,
            cwd=cwd)

        thread.join()

        assert data["command"] == "sleep 2"
        assert data["returncode"] == signal.SIGTERM
        assert data["stdout"] == ""
        assert data["exec_time"] > 0
        assert data["env"] == env
        assert data["cwd"] == cwd
