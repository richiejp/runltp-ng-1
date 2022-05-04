"""
Unittests for SUT package.
"""
import os
import time
import threading
import pytest
from ltp.sut import LocalSUT
from ltp.sut import QemuSUT
from ltp.sut import SSHSUT
from ltp.sut.base import SUTError

TEST_QEMU_IMAGE = os.environ.get("TEST_QEMU_IMAGE", None)
TEST_QEMU_PASSWORD = os.environ.get("TEST_QEMU_PASSWORD", None)


class TestLocalSUT:
    """
    Test LocalSUT implementation.
    """

    def test_communicate(self):
        """
        Test communicate method.
        """
        sut = LocalSUT()
        for i in range(0, 10):
            sut.communicate()
            sut.stop()

        sut.communicate()
        with pytest.raises(SUTError):
            sut.communicate()
        sut.stop()

    def test_communicate_run_cmd(self):
        """
        Test communicate method and use channel to run a command
        multiple times.
        """
        sut = LocalSUT()
        sut.communicate()

        assert sut.channel

        for _ in range(0, 100):
            ret = sut.channel.run_cmd("echo 'hello world'", 1)
            assert 'hello world\n' in ret["stdout"]
            assert ret["returncode"] == 0
            assert ret["exec_time"] > 0
            assert ret["timeout"] == 1
            assert ret["command"] == "echo 'hello world'"

        sut.stop(timeout=1)

    def test_stop_during_run_cmd(self, tmpdir):
        """
        Test stop method when running commands.
        """
        tmp = tmpdir / "tmp"
        tmp.mkdir()

        sut = LocalSUT()
        sut.communicate()

        assert sut.channel is not None

        def _threaded():
            start_t = time.time()
            while not sut.channel.is_running:
                assert time.time() - start_t < 5

            sut.stop(timeout=4)

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        ret = sut.channel.run_cmd("sleep 4", timeout=4)
        thread.join()

        assert ret["returncode"] != 0

    def test_force_stop_during_run_cmd(self, tmpdir):
        """
        Test force_stop method when running commands.
        """
        tmp = tmpdir / "tmp"
        tmp.mkdir()

        sut = LocalSUT()
        sut.communicate()

        assert sut.channel is not None

        def _threaded():
            start_t = time.time()
            while not sut.channel.is_running:
                assert time.time() - start_t < 5

            sut.force_stop(timeout=4)

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        ret = sut.channel.run_cmd("sleep 4", timeout=4)
        thread.join()

        assert ret["returncode"] != 0


@pytest.mark.skipif(TEST_QEMU_IMAGE is None, reason="TEST_QEMU_IMAGE is not defined")
@pytest.mark.skipif(TEST_QEMU_PASSWORD is None, reason="TEST_QEMU_IMAGE is not defined")
@pytest.mark.parametrize("image", [TEST_QEMU_IMAGE])
@pytest.mark.parametrize("password", [TEST_QEMU_PASSWORD])
class TestQemuSUT:
    """
    Test QemuSUT implementation.
    """

    def test_communicate(self, tmpdir, image, password):
        """
        Test communicate method.
        """
        sut = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password)

        sut.communicate()
        with pytest.raises(SUTError):
            sut.communicate()
        sut.stop()

    def test_stop_multiple_times(self, tmpdir, image, password):
        """
        Test stop when it's run multiple times.
        """
        sut = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password)

        sut.stop()
        sut.communicate()
        sut.stop()
        sut.stop()
        sut.stop()

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_communicate_run_cmd(self, tmpdir, image, password, serial):
        """
        Test communicate method and use runner object to execute
        commands on target.
        """
        sut = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            sut.communicate()

            assert sut.channel is not None

            for _ in range(0, 100):
                ret = sut.channel.run_cmd("echo 'hello world'", 1)
                assert 'hello world\n' in ret["stdout"]
                assert ret["returncode"] == 0
                assert ret["exec_time"] > 0
                assert ret["timeout"] == 1
                assert ret["command"] == "echo 'hello world'"
        finally:
            sut.stop()

    @pytest.mark.parametrize("force", [True, False])
    def test_stop_during_communicate(self, tmpdir, image, password, force):
        """
        Test stop method when running communicate.
        """
        sut = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password)

        def _threaded():
            time.sleep(1)

            if force:
                sut.force_stop(timeout=4)
            else:
                sut.stop(timeout=4)

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        sut.communicate()

        assert sut.channel is not None

        thread.join()

    @pytest.mark.parametrize("force", [True, False])
    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_stop_during_run_cmd(self, tmpdir, image, password, serial, force):
        """
        Test stop method when running a command.
        """
        sut = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            sut.communicate()

            assert sut.channel is not None

            def _threaded():
                start_t = time.time()
                while not sut.channel.is_running:
                    assert time.time() - start_t < 5

                if force:
                    sut.force_stop(timeout=10)
                else:
                    sut.stop(timeout=10)

            thread = threading.Thread(target=_threaded, daemon=True)
            thread.start()

            ret = sut.channel.run_cmd("sleep 4", timeout=10)
            thread.join()

            assert ret["returncode"] != 0
        finally:
            sut.stop()

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_communicate_fetch_file(self, tmpdir, image, password, serial):
        """
        Test communicate method and use channel object to download
        files from target to host.
        """
        sut = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            sut.communicate()

            assert sut.channel is not None

            for i in range(0, 100):
                target_path = f"/root/myfile{i}"
                local_path = str(tmpdir / f"myfile{i}")
                message = f"hello world{i}"

                # create file on target_path
                ret = sut.channel.run_cmd(
                    f"echo '{message}' > {target_path}", 1)
                assert ret["returncode"] == 0

                # download file in local_path
                sut.channel.fetch_file(target_path, local_path)
                with open(local_path, "r") as target:
                    assert target.read() == f"{message}\n"
        finally:
            sut.stop()

    @pytest.mark.xfail(reason="qemu serial protocol doesn't permit a real command stop")
    @pytest.mark.parametrize("force", [True, False])
    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_stop_during_fetch_file(self, tmpdir, image, password, serial, force):
        """
        Test stop method when fetching data.
        """
        target_path = f"/root/myfile"
        local_path = str(tmpdir / f"myfile")
        message = f"hello world"

        sut = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        sut.communicate()

        assert sut.channel is not None

        # create file on target_path
        ret = sut.channel.run_cmd(f"echo '{message}' > {target_path}")
        assert ret["returncode"] == 0

        def _threaded():
            start_t = time.time()
            while not sut.channel.is_running:
                assert time.time() - start_t < 5

            if force:
                sut.force_stop(timeout=10)
            else:
                sut.stop(timeout=10)

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        sut.channel.fetch_file(target_path, local_path)

        thread.join()

        with open(local_path, "r") as target:
            assert target.read() != f"{message}\n"

    def test_communicate_image_overlay(self, tmpdir, image, password):
        """
        Test communicate method when using image_overlay.
        """
        img_overlay = tmpdir / "image_overlay.qcow2"

        sut = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            image_overlay=img_overlay)

        try:
            sut.communicate()
        finally:
            sut.stop()

        assert os.path.isfile(img_overlay)

    def test_communicate_virtfs(self, tmpdir, image, password):
        """
        Test communicate method when using virtfs.
        """
        myfile = tmpdir / "myfile"
        myfile.write("")

        sut = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            virtfs=str(tmpdir))

        try:
            sut.communicate()

            ret = sut.channel.run_cmd(f"test -f /mnt/myfile", 1)
            assert ret["returncode"] == 0
        finally:
            sut.stop()


class TestSSHSUT:
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

    @pytest.mark.usefixtures("ssh_server")
    def test_communicate_run_cmd(self, config):
        """
        Test channel run_cmd after communicate.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        try:
            sut.communicate()

            assert sut.channel is not None

            for _ in range(0, 20):
                ret = sut.channel.run_cmd("echo 'hello world'", 1)
                assert 'hello world\n' in ret["stdout"]
                assert ret["returncode"] == 0
                assert ret["exec_time"] > 0
                assert ret["timeout"] == 1
                assert ret["command"] == "echo 'hello world'"
        finally:
            sut.stop()

    @pytest.mark.usefixtures("ssh_server")
    @pytest.mark.parametrize("force", [True, False])
    def test_stop_run_cmd(self, config, force):
        """
        Test stop after run_cmd.
        """
        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        sut.communicate()

        assert sut.channel is not None

        def _threaded():
            start_t = time.time()
            while not sut.channel.is_running:
                assert time.time() - start_t < 10

            if force:
                sut.force_stop(timeout=5)
            else:
                sut.stop(timeout=5)

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        ret = sut.channel.run_cmd("sleep 4")

        thread.join()

        assert ret["returncode"] != 0

    @pytest.mark.usefixtures("ssh_server")
    def test_communicate_fetch_file(self, tmpdir, config):
        """
        Test channel fetch_file after communicate.
        """
        target_folder = tmpdir.mkdir("target")

        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        try:
            sut.communicate()

            assert sut.channel is not None

            for i in range(0, 20):
                target_path = f"/{str(target_folder)}/myfile{i}"
                message = f"hello world{i}"

                with open(target_path, "w") as tpath:
                    tpath.write(message)

                local_path = str(tmpdir / f"myfile{i}")

                # download file in local_path
                sut.channel.fetch_file(target_path, local_path)
                with open(local_path, "r") as target:
                    assert target.read() == f"{message}"
        finally:
            sut.stop()

    @pytest.mark.usefixtures("ssh_server")
    @pytest.mark.parametrize("force", [True, False])
    def test_force_stop_fetch_file(self, tmpdir, config, force):
        """
        Test force_stop after fetch_file.
        """
        target_folder = tmpdir.mkdir("target")

        sut = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        sut.communicate()

        assert sut.channel is not None

        def _threaded():
            start_t = time.time()
            while not sut.channel.is_running:
                assert time.time() - start_t < 10

            if force:
                sut.force_stop(timeout=5)
            else:
                sut.stop(timeout=5)

        thread = threading.Thread(target=_threaded, daemon=True)
        thread.start()

        target_path = f"/{str(target_folder)}/myfile"
        message = "hello world"

        with open(target_path, "w") as tpath:
            tpath.write(message)

        local_path = str(tmpdir / "myfile")

        # download file in local_path
        sut.channel.fetch_file(target_path, local_path)

        thread.join()
