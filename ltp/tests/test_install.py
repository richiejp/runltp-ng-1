"""
Tests for install module
"""
import os
import pytest
from ltp.install import Installer, InstallerError


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

    @pytest.mark.parametrize("m32_support", [False, True])
    def test_install(self, m32_support, tmpdir):
        """
        Test install method
        """
        repo_dir = str(tmpdir / "repo")
        inst_dir = str(tmpdir / "ltp_install")
        installer = Installer(m32_support=m32_support)

        if "alpine" in installer.get_distro() and m32_support:
            pytest.skip("alpine doesn't support 32bit installation")

        installer.install(
            "https://github.com/linux-test-project/ltp.git",
            repo_dir,
            inst_dir)

        assert os.path.isfile(inst_dir + "/runltp")
        assert os.path.isdir(inst_dir + "/runtest")
        assert os.path.isdir(inst_dir + "/testcases")
        assert os.path.isdir(inst_dir + "/testscripts")
        assert os.path.isdir(inst_dir + "/scenario_groups")

    def test_install_bad_distro(self, tmpdir, mocker):
        """
        Test install method with bad distro ID.
        """
        def my_get_distro(*args, **kwargs):
            return "unsupported-distro"

        mocker.patch.object(Installer, 'get_distro', my_get_distro)

        repo_dir = str(tmpdir / "repo")
        inst_dir = str(tmpdir / "ltp_install")

        installer = Installer()

        with pytest.raises(InstallerError):
            installer.install(
                "https://github.com/linux-test-project/ltp.git",
                repo_dir,
                inst_dir)
