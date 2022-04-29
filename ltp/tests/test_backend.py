"""
Unittests for SUT package.
"""
import os
import pytest
from ltp.sut import SUT
from ltp.sut import LocalSUT
from ltp.sut import LocalSUTFactory
from ltp.sut import QemuSUT
from ltp.sut.ssh import SSHSUT, SSHSUTFactory
from ltp.metadata import RuntestMetadata

TEST_QEMU_IMAGE = os.environ.get("TEST_QEMU_IMAGE", None)
TEST_QEMU_PASSWORD = os.environ.get("TEST_QEMU_PASSWORD", None)


class TestLocalSUT:
    """
    Test LocalSUT implementation.
    """

    @pytest.mark.usefixtures("prepare_tmpdir")
    def test_communicate(self, tmpdir):
        """
        Test communicate method.
        """
        tmp = tmpdir / "tmp"
        tmp.mkdir()

        SUT = LocalSUT()
        SUT.communicate()

        assert SUT.downloader is not None
        assert SUT.runner is not None

        target_file = tmpdir / "runtest" / "dirsuite0"
        local_file = tmpdir / "tmp" / "dirsuite0"

        SUT.downloader.fetch_file(target_file, local_file)
        metadata = RuntestMetadata()
        suite = metadata.read_suite(local_file)

        testcases = tmpdir / "testcases" / "bin"

        for test in suite.tests:
            cmd = f"{test.command} {' '.join(test.arguments)}"
            result = SUT.runner.run_cmd(
                cmd,
                timeout=10,
                cwd=str(tmpdir),
                env={"PATH": f"$PATH:{str(testcases)}"})

            assert result is not None
            assert result["returncode"] == 0

    def test_factory(self):
        """
        Test LocalSUTFactory create() method with good arguments..
        """
        factory = LocalSUTFactory()
        SUT = factory.create()

        assert isinstance(SUT, SUT)


@pytest.mark.skipif(TEST_QEMU_IMAGE is None, reason="TEST_QEMU_IMAGE is not defined")
@pytest.mark.skipif(TEST_QEMU_PASSWORD is None, reason="TEST_QEMU_IMAGE is not defined")
@pytest.mark.parametrize("image", [TEST_QEMU_IMAGE])
@pytest.mark.parametrize("password", [TEST_QEMU_PASSWORD])
class TestQemuSUT:
    """
    Test QemuSUT implementation.
    """

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_communicate_runner(self, tmpdir, image, password, serial):
        """
        Test communicate method and use runner object to execute
        commands on target.
        """
        SUT = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            SUT.communicate()

            assert SUT.runner is not None

            for _ in range(0, 100):
                ret = SUT.runner.run_cmd("echo 'hello world'", 1)
                assert 'hello world\n' in ret["stdout"]
                assert ret["returncode"] == 0
                assert ret["exec_time"] > 0
                assert ret["timeout"] == 1
                assert ret["command"] == "echo 'hello world'"
        finally:
            SUT.stop()

    @pytest.mark.parametrize("serial", ["isa", "virtio"])
    def test_communicate_downloader(self, tmpdir, image, password, serial):
        """
        Test communicate method and use downloader object to download
        files from target to host.
        """
        SUT = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            serial=serial)

        try:
            SUT.communicate()

            assert SUT.runner is not None
            assert SUT.downloader is not None

            for i in range(0, 100):
                target_path = f"/root/myfile{i}"
                local_path = str(tmpdir / f"myfile{i}")
                message = f"hello world{i}"

                # create file on target_path
                ret = SUT.runner.run_cmd(
                    f"echo '{message}' > {target_path}", 1)
                assert ret["returncode"] == 0

                # download file in local_path
                SUT.downloader.fetch_file(target_path, local_path)
                with open(local_path, "r") as target:
                    assert target.read() == f"{message}\n"
        finally:
            SUT.stop()

    def test_communicate_image_overlay(self, tmpdir, image, password):
        """
        Test communicate method when using image_overlay.
        """
        img_overlay = tmpdir / "image_overlay.qcow2"

        SUT = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            image_overlay=img_overlay)

        try:
            SUT.communicate()
        finally:
            SUT.stop()

        assert os.path.isfile(img_overlay)

    def test_communicate_virtfs(self, tmpdir, image, password):
        """
        Test communicate method when using virtfs.
        """
        myfile = tmpdir / "myfile"
        myfile.write("")

        SUT = QemuSUT(
            tmpdir=str(tmpdir),
            image=image,
            password=password,
            virtfs=str(tmpdir))

        try:
            SUT.communicate()

            ret = SUT.runner.run_cmd(f"test -f /mnt/myfile", 1)
            assert ret["returncode"] == 0
        finally:
            SUT.stop()


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
    def test_communicate_runner(self, config):
        """
        Test runner after communicate.
        """
        SUT = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        try:
            SUT.communicate()

            assert SUT.runner is not None

            for _ in range(0, 20):
                ret = SUT.runner.run_cmd("echo 'hello world'", 1)
                assert 'hello world\n' in ret["stdout"]
                assert ret["returncode"] == 0
                assert ret["exec_time"] > 0
                assert ret["timeout"] == 1
                assert ret["command"] == "echo 'hello world'"
        finally:
            SUT.stop()

    @pytest.mark.usefixtures("ssh_server")
    def test_communicate_downloader(self, tmpdir, config):
        """
        Test downloader after communicate.
        """
        target_folder = tmpdir.mkdir("target")

        SUT = SSHSUT(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        try:
            SUT.communicate()

            assert SUT.runner is not None
            assert SUT.downloader is not None

            for i in range(0, 20):
                target_path = f"/{str(target_folder)}/myfile{i}"
                message = f"hello world{i}"

                with open(target_path, "w") as tpath:
                    tpath.write(message)

                local_path = str(tmpdir / f"myfile{i}")

                # download file in local_path
                SUT.downloader.fetch_file(target_path, local_path)
                with open(local_path, "r") as target:
                    assert target.read() == f"{message}"
        finally:
            SUT.stop()

    def test_factory(self, config):
        """
        Test SSHSUTFactory create() method.
        """
        factory = SSHSUTFactory(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key)

        SUT = factory.create()

        assert isinstance(SUT, SUT)
