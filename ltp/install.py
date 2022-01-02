"""
.. module:: install
    :platform: Linux
    :synopsis: module that contains LTP installer definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import logging
import configparser
import subprocess


class InstallerError(Exception):
    """
    Raised when an error occurs during LTP install.
    """


class Installer:
    """
    LTP installer from git repository.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("ltp.installer")

    def _run_cmd(self, cmd: str, cwd: str = None, raise_err=True) -> None:
        """
        Run a command inside the shell
        """
        self._logger.info("Running command '%s'", cmd)

        with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=cwd,
                shell=True,
                universal_newlines=True) as proc:

            for line in iter(proc.stdout.readline, b''):
                if not line:
                    break

                self._logger.info(line.rstrip())

            proc.wait()

        if raise_err and proc.returncode != 0:
            raise InstallerError(f"'{cmd}' return code: {proc.returncode}")

    def _clone_repo(self, url: str, repo_dir: str) -> None:
        """
        Run LTP installation from Git repository.
        :param url: url of the git repository.
        :type url: str
        :param repo_dir: repository output directory.
        :type repo_dir: str
        :raises: InstallerError
        """
        self._logger.info("Cloning repository..")

        self._run_cmd(f"git clone --depth=1 {url} {repo_dir}")

    def _install_from_src(self, repo_dir: str, install_dir: str) -> None:
        """
        Run LTP installation from Git repository.
        :param url: url of the git repository.
        :type url: str
        :param repo_dir: repository output directory.
        :type repo_dir: str
        :param install_dir: LTP installation directory.
        :type install_dir: str
        :raises: InstallerError
        """
        self._logger.info("Compiling sources..")

        cpus = subprocess.check_output(
            ['getconf', '_NPROCESSORS_ONLN']).rstrip().decode("utf-8")

        self._run_cmd("make autotools", repo_dir)
        self._run_cmd("./configure --prefix=" + install_dir, repo_dir)
        self._run_cmd(f"make -j{cpus}", repo_dir)
        self._run_cmd("make install", repo_dir)

    def _install_requirements(self) -> None:
        """
        Install requirements for LTP installation according with the
        Linux distro.
        """
        self._logger.info("Installing requirements..")

        currdir = os.path.dirname(os.path.abspath(__file__))

        config = configparser.ConfigParser()
        config.read(os.path.join(currdir, "packages.ini"))

        # by default we are running openSUSE
        default = config["default"]
        inst_cmd = "zypper --non-interactive --ignore-unknown install "
        refr_cmd = "zypper --non-interactive refresh"
        distro_id = ""

        with open("/etc/os-release", "r", encoding='UTF-8') as data:
            for line in data:
                if line.startswith("ID="):
                    distro_id = line
                    break

        self._logger.info("Detected '%s' distro", distro_id)

        if "alpine" in distro_id:
            default.update(config["alpine"])
            refr_cmd = "apk update"
            inst_cmd = "apk add "
        elif "debian" in distro_id:
            # replace "$KERNVER$" with the kernel version
            arch = subprocess.check_output(
                ['dpkg', '--print-architecture']).rstrip().decode("utf-8")
            kernver = config["debian"]["kernel-devel"]
            kernver = kernver.replace("$KERNVER$", arch)
            config["debian"]["kernel-devel"] = kernver

            default.update(config["debian"])
            refr_cmd = "apt-get -y update"
            inst_cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y install "
        elif "ubuntu" in distro_id:
            default.update(config["ubuntu"])
            refr_cmd = "apt-get -y update"
            inst_cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y install "
        elif "fedora" in distro_id:
            default.update(config["fedora"])
            refr_cmd = "yum update -y"
            inst_cmd = "yum install -y "

        pkgs = [value for _, value in default.items()]
        inst_cmd += " ".join(pkgs)

        self._run_cmd(refr_cmd, raise_err=False)
        self._run_cmd(inst_cmd)

    def install(self, url: str, repo_dir: str, install_dir: str) -> None:
        """
        Run LTP installation from Git repository.
        :param url: url of the git repository.
        :type url: str
        :param repo_dir: repository output directory.
        :type repo_dir: str
        :param install_dir: LTP installation directory.
        :type install_dir: str
        :raises: InstallerError
        """
        if not url:
            raise ValueError("url is empty")

        if not repo_dir:
            raise ValueError("repo_dir is empty")

        if not install_dir:
            raise ValueError("install_dir is empty")

        self._install_requirements()
        self._clone_repo(url, repo_dir)
        self._install_from_src(repo_dir, install_dir)
