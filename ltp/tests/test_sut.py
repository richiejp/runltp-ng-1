"""
Unittests for SUT package.
"""
import os
import time
import signal
import logging
import threading
import pytest
from ltp.sut import HostSUT
from ltp.sut import QemuSUT
from ltp.sut import SSHSUT
from ltp.sut import SUTError
from ltp.sut import SUTTimeoutError

TEST_QEMU_IMAGE = os.environ.get("TEST_QEMU_IMAGE", None)
TEST_QEMU_PASSWORD = os.environ.get("TEST_QEMU_PASSWORD", None)
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
        transfer_client.communicate()

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
            transfer_client.communicate()
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

        transfer_client.communicate()

        with pytest.raises(SUTTimeoutError):
            transfer_client.fetch_file(target, local, timeout=0)


class TestHostSUT:
    """
    Test HostSUT implementation.
    """

    @pytest.fixture
    def transfer_client(self):
        yield HostSUT()

    def test_communicate(self):
        """
        Test communicate method.
        """
        sut = HostSUT()
        for _ in range(0, 10):
            sut.communicate()
            sut.stop()

        sut.communicate()
        with pytest.raises(SUTError):
            sut.communicate()
        sut.stop()

    def test_run_command(self):
        """
        Test run_command method.
        """
        ret = HostSUT().run_command("test", timeout=1)
        assert ret["command"] == "test"
        assert ret["returncode"] == 1
        assert ret["stdout"] == ""
        assert ret["timeout"] == 1
        assert ret["exec_time"] > 0
        assert ret["cwd"] is None
        assert ret["env"] is None

    def test_run_command_timeout(self):
        """
        Test run_command method when timeout occurs.
        """
        channel = HostSUT()
        with pytest.raises(SUTTimeoutError):
            channel.run_command("sleep 10", timeout=0)

    def test_run_command_cwd(self, tmpdir):
        """
        Test run_command method using cwd initialization.
        """
        tmpfile = tmpdir / "myfile"
        tmpfile.write("")

        ret = HostSUT().run_command("ls", timeout=10, cwd=str(tmpdir))
        assert ret["command"] == "ls"
        assert ret["returncode"] == 0
        assert ret["stdout"] == "myfile\n"
        assert ret["timeout"] == 10
        assert ret["exec_time"] > 0
        assert ret["cwd"] == str(tmpdir)
        assert ret["env"] is None

    def test_run_command_env(self):
        """
        Test run_command method using environment variables.
        """
        env = dict(HELLO="world")
        ret = HostSUT().run_command(
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

    def test_stop_run_command(self):
        """
        Test stop method.
        """
        shell = HostSUT()

        class MyThread(threading.Thread):
            def __init__(self):
                super(MyThread, self).__init__()
                self.result = None
                self.daemon = True

            def run(self):
                self.result = shell.run_command("sleep 10", timeout=20)

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

    def test_run_command_timeout(self):
        """
        Test run_command on timeout
        """
        shell = HostSUT()
        shell.communicate()

        with pytest.raises(SUTTimeoutError):
            shell.run_command("test", timeout=0)


@pytest.mark.qemu
@pytest.mark.skipif(TEST_QEMU_IMAGE is None, reason="TEST_QEMU_IMAGE is not defined")
@pytest.mark.skipif(TEST_QEMU_PASSWORD is None, reason="TEST_QEMU_IMAGE is not defined")
@pytest.mark.parametrize("image", [TEST_QEMU_IMAGE])
@pytest.mark.parametrize("password", [TEST_QEMU_PASSWORD])
class TestQemuSUT(_TestDataTransfer):
    """
    Test QemuSUT implementation.
    """

    _logger = logging.getLogger("test.sut.qemu")

    @pytest.fixture
    def qemu(self, tmpdir, image, password):
        runner = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password)

        yield runner

    @pytest.fixture
    def transfer_client(self, qemu):
        yield qemu

    def test_communicate(self, qemu):
        """
        Test communicate method.
        """
        qemu.communicate(self._logger.info)
        with pytest.raises(SUTError):
            qemu.communicate(self._logger.info)
        qemu.stop()

    @pytest.mark.parametrize("force", [True, False])
    def test_stop_communicate(self, qemu, force):
        """
        Test stop method when running communicate.
        """
        def _threaded():
            time.sleep(1)

            if force:
                qemu.force_stop(timeout=4)
            else:
                qemu.stop(timeout=4)

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        qemu.communicate(self._logger.info)

        thread.join()

    @pytest.mark.parametrize("force", [True, False])
    def test_stop_multiple_times(self, qemu, force):
        """
        Test stop when it's run multiple times.
        """
        if force:
            qemu.force_stop(timeout=10)
        else:
            qemu.stop(timeout=10)

        qemu.communicate(self._logger.info)

        if force:
            qemu.force_stop(timeout=10)
        else:
            qemu.stop(timeout=10)

        if force:
            qemu.force_stop(timeout=10)
        else:
            qemu.stop(timeout=10)

        if force:
            qemu.force_stop(timeout=10)
        else:
            qemu.stop(timeout=10)

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_run_command(self, tmpdir, serial, image, password):
        """
        Test command run.
        """
        env = {"MYVAR": "hello"}

        qemu = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            qemu.communicate(self._logger.info)

            for _ in range(0, 100):
                data = qemu.run_command(
                    "echo $PWD-$MYVAR",
                    timeout=1,
                    env=env,
                    cwd="/tmp")
                assert data["command"] == "echo $PWD-$MYVAR"
                assert data["timeout"] == 1
                assert data["returncode"] == 0
                assert f"/tmp-hello" in data["stdout"]
                assert data["exec_time"] > 0
                assert data["env"] == env
                assert data["cwd"] == "/tmp"
        finally:
            qemu.stop()

    @pytest.mark.parametrize("force", [True, False])
    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_stop_run_command(self, tmpdir, image, password, serial, force):
        """
        Test stop method when running a command.
        """
        qemu = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            qemu.communicate(self._logger.info)

            def _threaded():
                start_t = time.time()
                while not qemu.is_running:
                    assert time.time() - start_t < 10

                time.sleep(1)

                if force:
                    qemu.force_stop(timeout=10)
                else:
                    qemu.stop(timeout=10)

            thread = threading.Thread(target=_threaded, daemon=True)
            thread.start()

            ret = qemu.run_command("sleep 5", timeout=10)
            thread.join()

            assert ret["returncode"] != 0
        finally:
            qemu.stop()

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_run_command_timeout(self, tmpdir, image, password, serial):
        """
        Test timeout on command run.
        """
        qemu = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            qemu.communicate(self._logger.info)

            with pytest.raises(SUTTimeoutError):
                qemu.run_command("sleep 5", timeout=0)
        finally:
            qemu.stop()

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_fetch_file(self, tmpdir, image, password, serial):
        """
        Test downloading files from target to host.
        """
        qemu = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            qemu.communicate(self._logger.info)

            for i in range(0, 100):
                target_path = f"/root/myfile{i}"
                local_path = str(tmpdir / f"myfile{i}")
                message = f"hello world{i}"

                # create file on target_path
                ret = qemu.run_command(
                    f"echo '{message}' > {target_path}", 1)
                assert ret["returncode"] == 0

                # download file in local_path
                qemu.fetch_file(target_path, local_path)
                with open(local_path, "r") as target:
                    assert target.read() == f"{message}\n"
        finally:
            qemu.stop()

    @pytest.mark.parametrize("force", [True, False])
    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_stop_fetch_file(self, tmpdir, image, password, serial, force):
        """
        Test stop method when fetching data.
        """
        target_path = f"/root/myfile"
        local_path = str(tmpdir / f"myfile")
        message = f"hello world"

        qemu = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        qemu.communicate(self._logger.info)

        # create file on target_path
        ret = qemu.run_command(f"echo '{message}' > {target_path}")
        assert ret["returncode"] == 0

        def _threaded():
            start_t = time.time()
            while not qemu.is_running:
                assert time.time() - start_t < 5

            if force:
                qemu.force_stop(timeout=10)
            else:
                qemu.stop(timeout=10)

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        qemu.fetch_file(target_path, local_path)

        thread.join()

        with open(local_path, "r") as target:
            assert target.read() != f"{message}"

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_fetch_file_timeout(self, tmpdir, image, password, serial):
        """
        Test timeout when downloading files from target to host.
        """
        qemu = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            qemu.communicate(self._logger.info)

            # create file on target_path
            ret = qemu.run_command(
                f"echo 'hello world' > /root/myfile", timeout=1)
            assert ret["returncode"] == 0

            with pytest.raises(SUTTimeoutError):
                qemu.fetch_file("/root/myfile", "myfile", timeout=0)
        finally:
            qemu.stop()

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_communicate_image_overlay(self, tmpdir, image, password, serial):
        """
        Test communicate method when using image_overlay.
        """
        img_overlay = tmpdir / "image_overlay.qcow2"

        qemu = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial,
            image_overlay=img_overlay)

        try:
            qemu.communicate(self._logger.info)
        finally:
            qemu.stop()

        assert os.path.isfile(img_overlay)

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_communicate_virtfs(self, tmpdir, image, password, serial):
        """
        Test communicate method when using virtfs.
        """
        myfile = tmpdir / "myfile"
        myfile.write("")

        qemu = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial,
            virtfs=str(tmpdir))

        try:
            qemu.communicate(self._logger.info)

            ret = qemu.run_command(f"test -f /mnt/myfile", 1)
            assert ret["returncode"] == 0
        finally:
            qemu.stop()


@pytest.mark.ssh
@pytest.mark.usefixtures("ssh_server")
class TestSSHSUT(_TestDataTransfer):
    """
    Test the SSHSUT implementation.
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
        yield SSHSUT(
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
            SSHSUT(
                host=None,
                port=config.port,
                user=config.user,
                key_file=config.user_key)

        with pytest.raises(ValueError):
            SSHSUT(
                host=config.hostname,
                port=-100,
                user=config.user,
                key_file=config.user_key)

        with pytest.raises(ValueError):
            SSHSUT(
                host=config.hostname,
                port=config.port,
                user=None,
                key_file=config.user_key)

        with pytest.raises(ValueError):
            SSHSUT(
                host=config.hostname,
                port=config.port,
                user=config.user,
                key_file="this_key_doesnt_exist.key")

    def test_bad_hostname(self, config):
        """
        Test connection when a bad hostname is given.
        """
        sut = SSHSUT(
            host="127.0.0.2",
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        with pytest.raises(SUTError):
            sut.communicate()

        sut.stop()

    def test_bad_port(self, config):
        """
        Test connection when a bad port is given.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=12345,
            user=config.user,
            key_file=config.user_key)

        with pytest.raises(SUTError):
            sut.communicate()

        sut.stop()

    def test_bad_user(self, config):
        """
        Test connection when a bad user is given.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user="this_user_doesnt_exist",
            key_file=config.user_key)

        with pytest.raises(SUTError):
            sut.communicate()

        sut.stop()

    def test_bad_key_file(self, config):
        """
        Test connection when a bad key file is given.
        """
        testsdir = os.path.abspath(os.path.dirname(__file__))
        user_key_pub = os.path.sep.join([testsdir, 'id_rsa_bad'])

        with pytest.raises(SUTError):
            sut = SSHSUT(
                host=config.hostname,
                port=config.port,
                user=config.user,
                key_file=user_key_pub)
            sut.communicate()

        sut.stop()

    def test_bad_password(self, config):
        """
        Test connection when a bad password is given.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            password="wrong_password")

        with pytest.raises(SUTError):
            sut.communicate()

        sut.stop()

    def test_bad_auth(self, config):
        """
        Test a unsupported authentication method.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user)

        with pytest.raises(SUTError):
            sut.communicate()

    def test_is_running(self, config):
        """
        Test is_running property.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        sut.communicate()

        def _threaded():
            start_t = time.time()
            while not sut.is_running:
                time.sleep(0.05)
                assert time.time() - start_t < 5

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        sut.run_command("sleep 0.5")

        thread.join()
        time.sleep(1)
        sut.stop()

    def test_connection_key_file(self, tmpdir, config):
        """
        Test connection using key_file.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        sut.communicate()

        env = {"MYVAR": "hello"}
        cwd = str(tmpdir)

        data = sut.run_command(
            "echo $PWD-$MYVAR",
            timeout=1,
            env=env,
            cwd=cwd)
        sut.stop()

        assert data["command"] == "echo $PWD-$MYVAR"
        assert data["timeout"] == 1
        assert data["returncode"] == 0
        assert data["stdout"] == f"{str(tmpdir)}-hello\n"
        assert data["exec_time"] > 0
        assert data["env"] == env
        assert data["cwd"] == cwd

    def test_run_command(self, config):
        """
        Test channel run_command after communicate.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        try:
            sut.communicate()

            for _ in range(0, 20):
                ret = sut.run_command("echo 'hello world'", 1)
                assert 'hello world' in ret["stdout"]
                assert ret["returncode"] == 0
                assert ret["exec_time"] > 0
                assert ret["timeout"] == 1
                assert ret["command"] == "echo 'hello world'"
        finally:
            sut.stop()

    @pytest.mark.parametrize("force", [True, False])
    def test_stop_run_command(self, config, force):
        """
        Test stop after run_command.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        sut.communicate()

        def _threaded():
            start_t = time.time()
            while not sut.is_running:
                assert time.time() - start_t < 10

            time.sleep(1)

            if force:
                sut.force_stop(timeout=5)
            else:
                sut.stop(timeout=5)

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        ret = sut.run_command("sleep 4")

        thread.join()

        assert ret["returncode"] != 0

    def test_run_command_timeout(self, config):
        """
        Test run_command when going in timeout.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        sut.communicate()

        with pytest.raises(SUTTimeoutError):
            sut.run_command("sleep 4", timeout=0)

    @pytest.mark.skipif(TEST_SSH_PASSWORD is None, reason="Empty SSH password")
    def test_connection_user_password(self, tmpdir, config):
        """
        Test connection using username/password.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            password=TEST_SSH_PASSWORD)

        env = {"MYVAR": "hello"}
        cwd = str(tmpdir)

        sut.communicate()

        data = sut.run_command(
            "echo $PWD-$MYVAR",
            timeout=1,
            env=env,
            cwd=cwd)
        sut.stop()

        assert data["command"] == "echo $PWD-$MYVAR"
        assert data["timeout"] == 1
        assert data["returncode"] == 0
        assert data["stdout"] == f"{str(tmpdir)}-hello\n"
        assert data["exec_time"] > 0
        assert data["env"] == env
        assert data["cwd"] == cwd
