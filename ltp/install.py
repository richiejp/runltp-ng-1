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

    def __init__(self, m32_support: bool = False) -> None:
        """
        :param m32_support: if True, LTP will be installed using 32bit support
        :type m32_support: bool
        """
        self._logger = logging.getLogger("ltp.installer")
        self._m32_support = m32_support

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
        """
        self._logger.info("Cloning repository..")
        self._run_cmd(f"git clone --depth=1 {url} {repo_dir}")
        self._logger.info("Cloning completed")

    def _install_from_src(self, repo_dir: str, install_dir: str) -> None:
        """
        Run LTP installation from Git repository.
        """
        self._logger.info("Compiling sources")

        cpus = subprocess.check_output(
            ['getconf', '_NPROCESSORS_ONLN']).rstrip().decode("utf-8")

        self._run_cmd("make autotools", repo_dir)
        self._run_cmd("./configure --prefix=" + install_dir, repo_dir)
        self._run_cmd(f"make -j{cpus}", repo_dir)
        self._run_cmd("make install", repo_dir)

        self._logger.info("Compiling completed")

    def _get_opensuse_pkgs(self) -> list:
        """
        Return openSUSE packages.
        """
        tools = [
            "git",
            "unzip",
            "autoconf",
            "automake",
            "pkg-config",
            "make",
            "gcc",
            "bc",
            "dosfstools",
            "xfsprogs",
            "e2fsprogs",
            "btrfsprogs",
            "quota",
            "nfs-kernel-server",
            "kernel-devel",
        ]

        pkgs = None

        if self._m32_support:
            pkgs = [
                "libaio-devel-32bit",
                "libacl-devel-32bit",
                "libattr-devel-32bit",
            ]
        else:
            pkgs = [
                "libaio-devel",
                "libacl-devel",
                "libattr-devel",
                "libcap-devel",
                "libnuma-devel",
            ]

        pkgs.extend(tools)

        return pkgs

    def _get_debian_derivative_packages(self, derivative: str = "") -> list:
        """
        Return Debian derivatives (Debian/Ubuntu) packages.
        """
        tools = [
            "git",
            "unzip",
            "autoconf",
            "automake",
            "pkg-config",
            "make",
            "bc",
            "dosfstools",
            "xfsprogs",
            "e2fsprogs",
            "btrfs-progs",
            "quota",
            "nfs-kernel-server",
        ]

        if "ubuntu" in derivative:
            tools.append("linux-headers-generic")
        else:
            arch = subprocess.check_output(
                ['dpkg', '--print-architecture']).rstrip().decode("utf-8")
            tools.append(f"linux-headers-{arch}")

        pkgs = None

        if self._m32_support:
            tools.append("gcc-multilib")
            pkgs = [
                "libaio-dev:i386",
                "libacl1-dev:i386",
                "libattr1-dev:i386",
                "libcap-dev:i386",
                "libnuma-dev:i386",
            ]
        else:
            tools.append("gcc")
            pkgs = [
                "libaio-dev",
                "libacl1-dev",
                "libattr1-dev",
                "libcap-dev",
                "libnuma-dev",
            ]

        pkgs.extend(tools)

        return pkgs

    # pylint: disable=no-self-use
    def _get_alpine_packages(self) -> list:
        """
        Return Alpine packages.
        """
        pkgs = [
            "git",
            "unzip",
            "autoconf",
            "automake",
            "pkgconf",
            "make",
            "build-base",
            "bc",
            "dosfstools",
            "xfsprogs",
            "e2fsprogs",
            "btrfs-progs",
            "quota-tools",
            "nfs-utils",
            "linux-headers",
            "libaio-dev",
            "acl-dev",
            "attr-dev",
            "libcap-dev",
            "numactl-dev",
        ]

        return pkgs

    def _get_fedora_packages(self) -> list:
        """
        Return Fedora packages.
        """
        tools = [
            "git",
            "unzip",
            "autoconf",
            "automake",
            "pkg-config",
            "make",
            "gcc",
            "bc",
            "dosfstools",
            "xfsprogs",
            "e2fsprogs",
            "btrfs-progs",
            "quota",
            "nfs-utils",
            "kernel-devel",
        ]

        pkgs = None

        if self._m32_support:
            pkgs = [
                "libaio-devel.i686",
                "libacl-devel.i686",
                "libattr-devel.i686",
                "libcap-devel.i686",
                "numactl-libs.i686"
            ]
        else:
            pkgs = [
                "libaio-devel",
                "libacl-devel",
                "libattr-devel",
                "libcap-devel",
                "numactl-libs",
            ]

        pkgs.extend(tools)

        return pkgs

    def _install_requirements(self) -> None:
        """
        Install requirements for LTP installation according with Linux distro.
        """
        self._logger.info("Installing requirements")

        distro_id = self.get_distro()

        self._logger.info("Detected '%s' distro", distro_id)

        inst_cmd = None
        refr_cmd = None

        if "sles" in distro_id or "opensuse" in distro_id:
            refr_cmd = "zypper --non-interactive refresh"
            inst_cmd = "zypper --non-interactive --ignore-unknown install "
        elif "alpine" in distro_id:
            refr_cmd = "apk update"
            inst_cmd = "apk add "
        elif "debian" in distro_id:
            refr_cmd = "apt-get -y update"
            inst_cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y \
                       --no-install-recommends install "
        elif "ubuntu" in distro_id:
            refr_cmd = "apt-get -y update"
            inst_cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y \
                        --no-install-recommends install "
        elif "fedora" in distro_id:
            refr_cmd = "yum update -y"
            inst_cmd = "yum install -y "
        else:
            raise InstallerError(f"{distro_id} distro is not supported")

        pkgs = self.get_packages(distro_id)
        inst_cmd += " ".join(pkgs)

        # add 32bit support on debian derivatives
        if "debian" in distro_id or "ubuntu" in distro_id:
            if self._m32_support:
                self._logger.info("Enabling i386 support in debian derivative")

                proc = subprocess.run(
                    ['dpkg', '--add-architecture', 'i386'], check=True)
                if proc.returncode != 0:
                    raise InstallerError(
                        f"Can't add i386 support on {distro_id}")

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

        if self._m32_support:
            if "alpine" in distro_id:
                raise InstallerError(
                    f"{distro_id} distro doesn't support 32bit installation")

        self._logger.info("Getting packages for %s", distro_id)

        pkgs = None

        if "sles" in distro_id or "opensuse" in distro_id:
            pkgs = self._get_opensuse_pkgs()
        elif "alpine" in distro_id:
            pkgs = self._get_alpine_packages()
        elif "debian" in distro_id:
            pkgs = self._get_debian_derivative_packages()
        elif "ubuntu" in distro_id:
            pkgs = self._get_debian_derivative_packages("ubuntu")
        elif "fedora" in distro_id:
            pkgs = self._get_fedora_packages()
        else:
            raise InstallerError(f"{distro_id} distro is not supported")

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
