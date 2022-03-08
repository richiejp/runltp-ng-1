"""
Tests for install module
"""
import os
import shutil
import pytest
from ltp.install import Installer, InstallerError
from ltp.install import main as main_run
from ltp.install import SUPPORTED_DISTROS


class TestPackages:
    """
    Tests for packages support in Installer class.
    """

    @pytest.mark.parametrize("distro", SUPPORTED_DISTROS)
    @pytest.mark.parametrize("m32", [True, False])
    def test_get_packages(self, distro, m32):
        """
        Test get_packages method
        """
        if distro == "debian" and not shutil.which("dpkg"):
            pytest.xfail("Running system doesn't have dpkg")

        if distro == "alpine" and m32:
            pytest.xfail("Alpine doesn't support 32bit")

        installer = Installer(m32_support=m32)
        pkgs = installer.get_packages(distro)

        assert "build" in pkgs
        assert "runtime" in pkgs
        assert "libs" in pkgs
        assert pkgs["build"] is not None
        assert pkgs["runtime"] is not None
        assert pkgs["libs"] is not None

    @pytest.mark.parametrize("distro", SUPPORTED_DISTROS)
    @pytest.mark.parametrize("pkgs", [
        "--build",
        "--runtime",
        "--build --runtime"])
    @pytest.mark.parametrize("m32", ["--m32", ""])
    def test_install_run(self, mocker, distro, pkgs, m32):
        """
        Test install_run function for the argparse function.
        """
        if distro == "debian" and not shutil.which("dpkg"):
            pytest.xfail("Running system doesn't have dpkg")

        mocker.patch("sys.argv", return_value=['--distro', distro, pkgs, m32])
        main_run()


@pytest.mark.skipif(os.geteuid() != 0, reason="this suite requires root")
class TestInstall:
    """
    Tests for installation in Installer class.
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
