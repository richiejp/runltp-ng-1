"""
Tests for install module
"""
import os
import pytest
from ltp.install import Installer


@pytest.mark.skipif(os.geteuid() != 0, reason="this suite requires root")
class TestInstaller:
    """
    Tests for Installer class.
    """

    def test_install_bad_args(self, tmpdir):
        """
        Test install method with bad arguments.
        """
        repo_dir = str(tmpdir / "repo")
        inst_dir = str(tmpdir / "ltp_install")
        installer = Installer()

        with pytest.raises(ValueError):
            installer.install(None, repo_dir, inst_dir)

        with pytest.raises(ValueError):
            installer.install("myrepo", None, inst_dir)

        with pytest.raises(ValueError):
            installer.install("myrepo", repo_dir, None)

    def test_install(self, tmpdir):
        """
        Test install method
        """
        repo_dir = str(tmpdir / "repo")
        inst_dir = str(tmpdir / "ltp_install")
        installer = Installer()

        installer.install(
            "https://github.com/linux-test-project/ltp.git",
            repo_dir,
            inst_dir)

        assert os.path.isfile(inst_dir + "/runltp")
        assert os.path.isdir(inst_dir + "/runtest")
        assert os.path.isdir(inst_dir + "/testcases")
        assert os.path.isdir(inst_dir + "/testscripts")
        assert os.path.isdir(inst_dir + "/scenario_groups")
