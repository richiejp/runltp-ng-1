"""
Tests for install module
"""
import os
import shutil
import pytest
import ltp.install
from ltp.install import main as main_run
from ltp.install import INSTALLERS


SUPPORTED_DISTROS = [pm.distro_id for pm in INSTALLERS]


@pytest.mark.parametrize("distro", SUPPORTED_DISTROS)
@pytest.mark.parametrize("build", ["--build", ""])
@pytest.mark.parametrize("runtime", ["--runtime", ""])
@pytest.mark.parametrize("m32", ["--m32", ""])
@pytest.mark.parametrize("cmd", ["--cmd", ""])
@pytest.mark.parametrize("tools", ["--tools", ""])
def test_install_run(mocker, distro, build, runtime, m32, cmd, tools):
    """
    Test install_run function for __main__
    """
    if distro == "debian" and not shutil.which("dpkg"):
        pytest.xfail("Running system doesn't have dpkg")

    mocker.patch("sys.argv", return_value=[
                 '--distro', distro, build, runtime, m32, cmd, tools])
    main_run()


@pytest.mark.skipif(os.geteuid() != 0, reason="this suite requires root")
class TestInstall:
    """
    Tests for installation in Installer class.
    """

    @pytest.mark.parametrize("m32_support", [False, True])
    def test_install_bad_args(self, m32_support, tmpdir):
        """
        Test install method with bad arguments.
        """
        repo_dir = str(tmpdir / "repo")
        inst_dir = str(tmpdir / "ltp_install")
        installer = ltp.install.get_installer()

        with pytest.raises(ValueError):
            installer.install(m32_support, None, repo_dir, inst_dir)

        with pytest.raises(ValueError):
            installer.install(m32_support, "myrepo", None, inst_dir)

        with pytest.raises(ValueError):
            installer.install(m32_support, "myrepo", repo_dir, None)

    @pytest.mark.parametrize("m32_support", [False, True])
    def test_install(self, m32_support, tmpdir):
        """
        Test install method
        """
        repo_dir = str(tmpdir / "repo")
        inst_dir = str(tmpdir / "ltp_install")
        installer = ltp.install.get_installer()

        if "alpine" in ltp.install.get_distro() and m32_support:
            pytest.skip("alpine doesn't support 32bit installation")

        installer.install(
            m32_support,
            "https://github.com/linux-test-project/ltp.git",
            repo_dir,
            inst_dir)

        assert os.path.isfile(inst_dir + "/runltp")
        assert os.path.isdir(inst_dir + "/runtest")
        assert os.path.isdir(inst_dir + "/testcases")
        assert os.path.isdir(inst_dir + "/testscripts")
        assert os.path.isdir(inst_dir + "/scenario_groups")
