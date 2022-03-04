"""
.. module:: install
    :platform: Linux
    :synopsis: module that contains LTP installer definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import logging
import subprocess


class InstallerError(Exception):
    """
    Raised when an error occurs during LTP install.
    """


class Installer:
    """
    LTP installer from git repository.
    """

    PACKAGES = dict(
        default=dict(
            git="git",
            unzip="unzip",
            autoconf="autoconf",
            automake="automake",
            pkg_config="pkg-config",
            make="make",
            gcc="gcc",
            bc="bc",
            dosfstools="dosfstools",
            xfstools="xfstools",
            e2fsprogs="e2fsprogs",
            btrfsprogs="btrfsprogs",
            quota="quota",
            nfs_utils="nfs-utils",
            kernel_devel="kernel-devel",
            libaio_devel="libaio-devel",
            libacl_devel="libacl-devel",
            libattr_devel="libattr-devel",
            libcap_devel="libcap-devel",
        ),
        alpine=dict(
            gcc="build-base",
            pkg_config="pkgconf",
            xfstools="xfsprogs",
            btrfsprogs="btrfs-progs",
            quota="quota-tools",
            kernel_devel="linux-headers",
            libaio_devel="libaio-dev",
            libacl_devel="acl-dev",
            libattr_devel="attr-dev",
            libcap_devel="libcap-dev",
            libnuma_devel="numactl-dev",
        ),
        debian=dict(
            xfstools="xfsprogs",
            btrfsprogs="btrfs-progs",
            nfs_utils="nfs-kernel-server",
            kernel_devel="linux-headers-$KERNVER$",
            libaio_devel="libaio-dev",
            libacl_devel="libacl1-dev",
            libattr_devel="libattr1-dev",
            libcap_devel="libcap-dev",
            libnuma_devel="libnuma-dev",
        ),
        fedora=dict(
            xfstools="xfsprogs",
            btrfsprogs="btrfs-progs",
            libaio_devel="libaio-devel",
            libacl_devel="libacl-devel",
            libattr_devel="libattr-devel",
            libcap_devel="libcap-devel",
            libnuma_devel="numactl-libs",
        ),
        ubuntu=dict(
            xfstools="xfsprogs",
            btrfsprogs="btrfs-progs",
            nfs_utils="nfs-kernel-server",
            kernel_devel="linux-headers-generic",
            libaio_devel="libaio-dev",
            libacl_devel="libacl1-dev",
            libattr_devel="libattr1-dev",
            libcap_devel="libcap-dev",
            libnuma_devel="libnuma-dev",
        ),
    )

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
        self._logger.info("Cloning completed")

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
        self._logger.info("Compiling sources")

        cpus = subprocess.check_output(
            ['getconf', '_NPROCESSORS_ONLN']).rstrip().decode("utf-8")

        self._run_cmd("make autotools", repo_dir)
        self._run_cmd("./configure --prefix=" + install_dir, repo_dir)
        self._run_cmd(f"make -j{cpus}", repo_dir)
        self._run_cmd("make install", repo_dir)

        self._logger.info("Compiling completed")

    def _install_requirements(self) -> None:
        """
        Install requirements for LTP installation according with the
        Linux distro.
        """
        self._logger.info("Installing requirements")

        distro_id = self.get_distro()
        pkgs = self.get_packages(distro_id)

        # by default we are running openSUSE
        inst_cmd = "zypper --non-interactive --ignore-unknown install "
        refr_cmd = "zypper --non-interactive refresh"

        self._logger.info("Detected '%s' distro", distro_id)

        if "alpine" in distro_id:
            refr_cmd = "apk update"
            inst_cmd = "apk add "
        elif "debian" in distro_id:
            refr_cmd = "apt-get -y update"
            inst_cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y install "
        elif "ubuntu" in distro_id:
            refr_cmd = "apt-get -y update"
            inst_cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y install "
        elif "fedora" in distro_id:
            refr_cmd = "yum update -y"
            inst_cmd = "yum install -y "

        inst_cmd += " ".join(pkgs)

        self._run_cmd(refr_cmd, raise_err=False)
        self._run_cmd(inst_cmd)

        self._logger.info("Installation completed")

    def get_distro(self) -> str:
        """
        Return distro name.
        :returns: str
        """
        distro_id = ""

        with open("/etc/os-release", "r", encoding='UTF-8') as data:
            for line in data:
                if line.startswith("ID="):
                    distro_id = line
                    break

        name = ""
        if distro_id:
            name = distro_id.rstrip().split('=')[1]

        self._logger.info("Detected %s distro", name)

        return name

    def get_packages(self, distro_id: str) -> list:
        """
        Return the list of packages which has to be installed according with
        the running operating system.
        :param distro_id: the ID given by /etc/os-release
        :type distro_id: str
        :returns: list
        """
        if not distro_id:
            raise ValueError("distro_id is empty")

        self._logger.info("Getting packages for %s", distro_id)

        default = self.PACKAGES["default"].copy()

        if "alpine" in distro_id:
            default.update(self.PACKAGES["alpine"])
        elif "debian" in distro_id:
            # replace "$KERNVER$" with the kernel version
            arch = subprocess.check_output(
                ['dpkg', '--print-architecture']).rstrip().decode("utf-8")
            kernver = self.PACKAGES["debian"]["kernel_devel"]
            kernver = kernver.replace("$KERNVER$", arch)
            self.PACKAGES["debian"]["kernel_devel"] = kernver

            default.update(self.PACKAGES["debian"])
        elif "ubuntu" in distro_id:
            default.update(self.PACKAGES["ubuntu"])
        elif "fedora" in distro_id:
            default.update(self.PACKAGES["fedora"])

        pkgs = [value for _, value in default.items()]

        self._logger.debug(pkgs)

        return pkgs

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
