"""
Unittests for Backend package.
"""
import os
import pytest
from ltp.backend import Backend
from ltp.backend import LocalBackend
from ltp.backend import LocalBackendFactory
from ltp.backend import QemuBackend
from ltp.backend.ssh import SSHBackend, SSHBackendFactory
from ltp.metadata import RuntestMetadata

TEST_QEMU_IMAGE = os.environ.get("TEST_QEMU_IMAGE", None)
TEST_QEMU_PASSWORD = os.environ.get("TEST_QEMU_PASSWORD", None)


class TestLocalBackend:
    """
    Test LocalBackend implementation.
    """

    @pytest.mark.usefixtures("prepare_tmpdir")
    def test_communicate(self, tmpdir):
        """
        Test communicate method.
        """
        tmp = tmpdir / "tmp"
        tmp.mkdir()

        backend = LocalBackend()
        backend.communicate()

        assert backend.downloader is not None
        assert backend.runner is not None

        target_file = tmpdir / "runtest" / "dirsuite0"
        local_file = tmpdir / "tmp" / "dirsuite0"

        backend.downloader.fetch_file(target_file, local_file)
        metadata = RuntestMetadata()
        suite = metadata.read_suite(local_file)

        testcases = tmpdir / "testcases" / "bin"

        for test in suite.tests:
            cmd = f"{test.command} {' '.join(test.arguments)}"
            result = backend.runner.run_cmd(
                cmd,
                timeout=10,
                cwd=str(tmpdir),
                env={"PATH": f"$PATH:{str(testcases)}"})

            assert result is not None
            assert result["returncode"] == 0

    def test_factory(self):
        """
        Test LocalBackendFactory create() method with good arguments..
        """
        factory = LocalBackendFactory()
        backend = factory.create()

        assert isinstance(backend, Backend)


@pytest.mark.skipif(TEST_QEMU_IMAGE is None, reason="TEST_QEMU_IMAGE is not defined")
@pytest.mark.skipif(TEST_QEMU_PASSWORD is None, reason="TEST_QEMU_IMAGE is not defined")
@pytest.mark.parametrize("image", [TEST_QEMU_IMAGE])
@pytest.mark.parametrize("password", [TEST_QEMU_PASSWORD])
class TestQemuBackend:
    """
    Test QemuBackend implementation.
    """

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_communicate_runner(self, tmpdir, image, password, serial):
        """
        Test communicate method and use runner object to execute
        commands on target.
        """
        backend = QemuBackend(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            backend.communicate()

            assert backend.runner is not None

            for _ in range(0, 100):
                ret = backend.runner.run_cmd("echo 'hello world'", 1)
                assert 'hello world\n' in ret["stdout"]
                assert ret["returncode"] == 0
                assert ret["exec_time"] > 0
                assert ret["timeout"] == 1
                assert ret["command"] == "echo 'hello world'"
        finally:
            backend.stop()

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_communicate_downloader(self, tmpdir, image, password, serial):
        """
        Test communicate method and use downloader object to download
        files from target to host.
        """
        backend = QemuBackend(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            backend.communicate()

            assert backend.runner is not None
            assert backend.downloader is not None

            for i in range(0, 100):
                target_path = f"/root/myfile{i}"
                local_path = str(tmpdir / f"myfile{i}")
                message = f"hello world{i}"

                # create file on target_path
                ret = backend.runner.run_cmd(
                    f"echo '{message}' > {target_path}", 1)
                assert ret["returncode"] == 0

                # download file in local_path
                backend.downloader.fetch_file(target_path, local_path)
                with open(local_path, "r") as target:
                    assert target.read() == f"{message}\n"
        finally:
            backend.stop()

    def test_communicate_image_overlay(self, tmpdir, image, password):
        """
        Test communicate method when using image_overlay.
        """
        img_overlay = tmpdir / "image_overlay.qcow2"

        backend = QemuBackend(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            image_overlay=img_overlay)

        try:
            backend.communicate()
        finally:
            backend.stop()

        assert os.path.isfile(img_overlay)

    def test_communicate_virtfs(self, tmpdir, image, password):
        """
        Test communicate method when using virtfs.
        """
        myfile = tmpdir / "myfile"
        myfile.write("")

        backend = QemuBackend(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            virtfs=str(tmpdir))

        try:
            backend.communicate()

            ret = backend.runner.run_cmd(f"test -f /mnt/myfile", 1)
            assert ret["returncode"] == 0
        finally:
            backend.stop()


class TestSSHBackend:
    """
    Test the SSHBackend implementation.
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
    def test_communicate_runner(self, config):
        """
        Test runner after communicate.
        """
        backend = SSHBackend(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        try:
            backend.communicate()

            assert backend.runner is not None

            for _ in range(0, 20):
                ret = backend.runner.run_cmd("echo 'hello world'", 1)
                assert 'hello world\n' in ret["stdout"]
                assert ret["returncode"] == 0
                assert ret["exec_time"] > 0
                assert ret["timeout"] == 1
                assert ret["command"] == "echo 'hello world'"
        finally:
            backend.stop()

    @pytest.mark.usefixtures("ssh_server")
    def test_communicate_downloader(self, tmpdir, config):
        """
        Test downloader after communicate.
        """
        target_folder = tmpdir.mkdir("target")

        backend = SSHBackend(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        try:
            backend.communicate()

            assert backend.runner is not None
            assert backend.downloader is not None

            for i in range(0, 20):
                target_path = f"/{str(target_folder)}/myfile{i}"
                message = f"hello world{i}"

                with open(target_path, "w") as tpath:
                    tpath.write(message)

                local_path = str(tmpdir / f"myfile{i}")

                # download file in local_path
                backend.downloader.fetch_file(target_path, local_path)
                with open(local_path, "r") as target:
                    assert target.read() == f"{message}"
        finally:
            backend.stop()

    def test_factory(self, config):
        """
        Test SSHBackendFactory create() method.
        """
        factory = SSHBackendFactory(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        backend = factory.create()

        assert isinstance(backend, Backend)
