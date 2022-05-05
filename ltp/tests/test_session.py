"""
Unittest for main module.
"""
import os
import pwd
import time
import pathlib
import pytest
from ltp.session import Session
from ltp.session import TempRotator

TEST_QEMU_IMAGE = os.environ.get("TEST_QEMU_IMAGE", None)
TEST_QEMU_PASSWORD = os.environ.get("TEST_QEMU_PASSWORD", None)


class TestTempRotator:
    """
    Test the TempRotator class implementation.
    """

    def test_constructor(self):
        """
        Test TempRotator constructor.
        """
        with pytest.raises(ValueError):
            TempRotator("this_folder_doesnt_exist")

    def test_rotate(self, tmpdir):
        """
        Test rotate method.
        """
        max_rotate = 5
        plus_rotate = 5

        currdir = str(tmpdir)
        rotator = TempRotator(currdir, max_rotate=max_rotate)

        paths = []
        for _ in range(0, max_rotate + plus_rotate):
            path = rotator.rotate()
            paths.append(path)

            # force cache IO operations
            os.sync()

        # just wait and re-sync to be sure about files removal
        time.sleep(0.5)
        os.sync()

        sorted_paths = sorted(
            pathlib.Path(rotator._tmpbase).iterdir(),
            key=os.path.getmtime)

        latest = None
        for path in sorted_paths:
            if path.name == "latest":
                latest = path
                break

        assert latest is not None
        assert os.readlink(str(path)) == paths[-1]

        paths_dir = [
            str(path) for path in sorted_paths
            if path.name != "latest"
        ]

        assert list(set(paths[plus_rotate:]) - set(paths_dir)) == []


class TestSession:
    """
    Tests for Session implementation.
    """

    @pytest.mark.usefixtures("prepare_tmpdir")
    @pytest.mark.parametrize("verbose", [True, False])
    @pytest.mark.parametrize("git_config", [dict(branch="master"), None])
    @pytest.mark.parametrize("use_report", [True, False])
    @pytest.mark.parametrize("suites", [None, ["dirsuite0", "dirsuite1"]])
    @pytest.mark.parametrize("command", [None, "ls -1"])
    def test_run_single_host(
            self,
            tmpdir,
            use_report,
            verbose,
            git_config,
            suites,
            command):
        """
        Test run_single on host SUT.
        """
        if git_config and os.geteuid() != 0:
            pytest.skip(msg="Must be root to install LTP")

        report_path = None
        if use_report:
            report_path = str(tmpdir / "report.json")

        session = Session(verbose=verbose)
        session.run_single(
            dict(name="host"),
            git_config,
            report_path,
            suites,
            command)

        if use_report and suites:
            assert os.path.isfile(report_path)

    @pytest.mark.ssh
    @pytest.mark.usefixtures("prepare_tmpdir", "ssh_server")
    @pytest.mark.parametrize("verbose", [True, False])
    @pytest.mark.parametrize("git_config", [dict(branch="master"), None])
    @pytest.mark.parametrize("use_report", [True, False])
    @pytest.mark.parametrize("suites", [None, ["dirsuite0", "dirsuite1"]])
    @pytest.mark.parametrize("command", [None, "ls -1"])
    def test_run_single_ssh(
            self,
            tmpdir,
            use_report,
            verbose,
            git_config,
            suites,
            command):
        """
        Test run_single on SSH sut.
        """
        user = pwd.getpwuid(os.geteuid()).pw_name
        if git_config and user != "root":
            pytest.skip(msg="Must be root to install LTP")

        report_path = None
        if use_report:
            report_path = str(tmpdir / "report.json")

        testsdir = os.path.abspath(os.path.dirname(__file__))
        key_file = os.path.sep.join([testsdir, 'id_rsa'])

        session = Session(verbose=verbose)
        session.run_single(
            {
                "name": "ssh",
                "host": "localhost",
                "port": 2222,
                "user": user,
                "key_file": key_file
            },
            git_config,
            report_path,
            suites,
            command)

        if use_report and suites:
            assert os.path.isfile(report_path)

    @pytest.mark.qemu
    @pytest.mark.skipif(TEST_QEMU_IMAGE is None, reason="TEST_QEMU_IMAGE is not defined")
    @pytest.mark.skipif(TEST_QEMU_PASSWORD is None, reason="TEST_QEMU_IMAGE is not defined")
    @pytest.mark.usefixtures("prepare_tmpdir")
    @pytest.mark.parametrize("verbose", [True, False])
    @pytest.mark.parametrize("git_config", [dict(branch="master"), None])
    @pytest.mark.parametrize("use_report", [True, False])
    @pytest.mark.parametrize("suites", [None, ["dirsuite0", "dirsuite1"]])
    @pytest.mark.parametrize("command", [None, "ls -1"])
    def test_run_single_qemu(
            self,
            tmpdir,
            verbose,
            git_config,
            use_report,
            suites,
            command):
        """
        Test run_single on Qemu host.
        """
        report_path = None
        if use_report:
            report_path = str(tmpdir / "report.json")

        session = Session(verbose=verbose)
        session.run_single(
            {
                "name": "qemu",
                "image": TEST_QEMU_IMAGE,
                "password": TEST_QEMU_PASSWORD,
                "image_overlay": "image_copy.qcow2"
            },
            git_config,
            report_path,
            suites,
            command)

        if use_report and suites:
            assert os.path.isfile(report_path)
