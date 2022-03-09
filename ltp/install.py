"""
.. module:: install
    :platform: Linux
    :synopsis: module that contains LTP installer definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import logging
import subprocess
import argparse
from argparse import Namespace


class PackageHandler:
    """
    A generic distro packages handler.
    """

    @property
    def name(self) -> str:
        """
        Name of the distro.
        """
        raise NotImplementedError()

    def setup_32bit(self) -> None:
        """
        Override this method if distro must be configured for
        32bit installation.
        """
        pass

    def get_build_pkgs(self, m32: bool) -> list:
        """
        Return build packages.
        """
        raise NotImplementedError()

    def get_runtime_pkgs(self, m32: bool) -> list:
        """
        Return runtime packages.
        """
        raise NotImplementedError()

    def get_libs_pkgs(self, m32: bool) -> list:
        """
        Return development libraries packages.
        """
        raise NotImplementedError()

    @property
    def refresh_cmd(self) -> str:
        """
        Cache refresh command.
        """
        raise NotImplementedError()

    @property
    def install_cmd(self) -> str:
        """
        Packages install command.
        """
        raise NotImplementedError()

    def get_all_pkgs(self, m32: bool) -> list:
        """
        Return all available packages.
        """
        pkgs = []

        pkgs.extend(self.get_build_pkgs(m32))
        pkgs.extend(self.get_runtime_pkgs(m32))
        pkgs.extend(self.get_libs_pkgs(m32))

        return pkgs

    def get_pkg_commands(self, packages: list) -> list:
        """
        Return commands used to install LTP dependences.
        """
        if not packages:
            raise ValueError("empty packages list")

        cmd = [
            self.refresh_cmd,
            f"{self.install_cmd} {' '.join(packages)}"
        ]

        return cmd


class OpenSUSEPackageHandler(PackageHandler):
    """
    PackageHandler for openSUSE.
    """

    @property
    def name(self) -> str:
        return "opensuse"

    def get_build_pkgs(self, _: bool) -> list:
        return [
            "make",
            "autoconf",
            "automake",
            "pkg-config",
            "gcc",
            "git",
            "unzip",
            "kernel-devel",
        ]

    def get_runtime_pkgs(self, _: bool) -> list:
        return [
            "dosfstools",
            "xfsprogs",
            "e2fsprogs",
            "btrfsprogs",
            "bc",
            "quota",
            "nfs-kernel-server",
        ]

    def get_libs_pkgs(self, m32: bool) -> list:
        pkgs = None
        if m32:
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

        return pkgs

    @property
    def refresh_cmd(self) -> str:
        return "zypper --non-interactive refresh"

    @property
    def install_cmd(self) -> str:
        return "zypper --non-interactive --ignore-unknown install"


class SLESPackageHandler(OpenSUSEPackageHandler):
    """
    PackageHandler for SLES.
    """

    @property
    def name(self) -> str:
        return "sles"


class DebianPackageHandler(PackageHandler):
    """
    PackageHandler for Debian.
    """

    @property
    def name(self) -> str:
        return "debian"

    def setup_32bit(self) -> None:
        proc = subprocess.run(
            ['dpkg', '--add-architecture', 'i386'], check=True)
        if proc.returncode != 0:
            raise InstallerError("Can't add i386 support on debian")

    def get_build_pkgs(self, m32: bool) -> list:
        pkgs = [
            "make",
            "automake",
            "autoconf",
            "pkg-config",
            "git",
            "unzip",
        ]

        if m32:
            pkgs.append("gcc-multilib")
        else:
            pkgs.append("gcc")

        return pkgs

    def get_runtime_pkgs(self, _: bool) -> list:
        pkgs = [
            "dosfstools",
            "xfsprogs",
            "e2fsprogs",
            "btrfs-progs",
            "bc",
            "quota",
            "nfs-kernel-server",
        ]

        arch = subprocess.check_output(
            ['dpkg', '--print-architecture']).rstrip().decode("utf-8")
        pkgs.append(f"linux-headers-{arch}")

        return pkgs

    def get_libs_pkgs(self, m32: bool) -> list:
        pkgs = None
        if m32:
            pkgs = [
                "libaio-dev:i386",
                "libacl1-dev:i386",
                "libattr1-dev:i386",
                "libcap-dev:i386",
                "libnuma-dev:i386",
            ]
        else:
            pkgs = [
                "libaio-dev",
                "libacl1-dev",
                "libattr1-dev",
                "libcap-dev",
                "libnuma-dev",
            ]

        return pkgs

    @property
    def refresh_cmd(self) -> str:
        return "apt-get -y update"

    @property
    def install_cmd(self) -> str:
        cmd = "DEBIAN_FRONTEND=noninteractive "
        cmd += "apt-get -y --no-install-recommends install"
        return cmd


class UbuntuPackageHandler(DebianPackageHandler):
    """
    PackageHandler for Ubuntu.
    """

    @property
    def name(self) -> str:
        return "ubuntu"

    def get_runtime_pkgs(self, _: bool) -> list:
        return [
            "dosfstools",
            "xfsprogs",
            "e2fsprogs",
            "btrfs-progs",
            "bc",
            "quota",
            "nfs-kernel-server",
            "linux-headers-generic",
        ]


class AlpinePackageHandler(PackageHandler):
    """
    PackageHandler for Alpine Linux.
    """

    @property
    def name(self) -> str:
        return "alpine"

    def get_build_pkgs(self, _: bool) -> list:
        return [
            "make",
            "automake",
            "autoconf",
            "pkgconf",
            "build-base",
            "git",
            "unzip",
            "linux-headers",
        ]

    def get_runtime_pkgs(self, _: bool) -> list:
        return [
            "dosfstools",
            "xfsprogs",
            "e2fsprogs",
            "btrfs-progs",
            "bc",
            "quota-tools",
            "nfs-utils",
        ]

    def get_libs_pkgs(self, m32: bool) -> list:
        if m32:
            raise InstallerError("Alpine doesn't support 32bit")

        return [
            "libaio-dev",
            "acl-dev",
            "attr-dev",
            "libcap-dev",
            "numactl-dev",
        ]

    @property
    def refresh_cmd(self) -> str:
        return "apk update"

    @property
    def install_cmd(self) -> str:
        return "apk add"


class FedoraPackageHandler(PackageHandler):
    """
    PackageHandler for Fedora.
    """

    @property
    def name(self) -> str:
        return "fedora"

    def get_build_pkgs(self, _: bool) -> list:
        return [
            "make",
            "automake",
            "autoconf",
            "pkg-config",
            "gcc",
            "git",
            "unzip",
            "kernel-devel",
        ]

    def get_runtime_pkgs(self, _: bool) -> list:
        return [
            "dosfstools",
            "xfsprogs",
            "e2fsprogs",
            "btrfs-progs",
            "bc",
            "quota",
            "nfs-utils",
        ]

    def get_libs_pkgs(self, m32: bool) -> list:
        pkgs = None

        if m32:
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

        return pkgs

    @property
    def refresh_cmd(self) -> str:
        return "yum update -y"

    @property
    def install_cmd(self) -> str:
        return "yum install -y"


PACKAGE_HANDLERS = [
    OpenSUSEPackageHandler(),
    SLESPackageHandler(),
    DebianPackageHandler(),
    UbuntuPackageHandler(),
    AlpinePackageHandler(),
    FedoraPackageHandler(),
]


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

    def _install_requirements(self, m32_support: bool) -> None:
        """
        Install requirements for LTP installation according with Linux distro.
        """
        self._logger.info("Installing requirements")

        distro_id = self.get_distro()
        handler = self.get_pkg_handler(distro_id)

        if m32_support:
            handler.setup_32bit()

        pkgs = handler.get_all_pkgs(m32_support)
        cmds = handler.get_pkg_commands(pkgs)

        self._run_cmd(cmds[0], raise_err=False)
        self._run_cmd(cmds[1])

        self._logger.info("Installation completed")

    def get_pkg_handler(self, distro_id: str) -> PackageHandler:
        """
        Return the proper package handler according with the distro name.
        """
        handler = None
        for item in PACKAGE_HANDLERS:
            if item.name == distro_id:
                handler = item
                break

        if not handler:
            raise InstallerError(f"{distro_id} is not supported")

        return handler

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

    def install(self,
                m32_support: bool,
                url: str,
                repo_dir: str,
                install_dir: str) -> None:
        """
        Run LTP installation from Git repository.
        :param m32_support: If True, 32bit support will be installed.
        :type m32_support: bool
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

        self._install_requirements(m32_support)
        self._clone_repo(url, repo_dir)
        self._install_from_src(repo_dir, install_dir)


def install_run(args: Namespace) -> None:
    """
    Run the installer main command.
    """
    if not args.build and not args.runtime:
        print("No packages selected!")
        return

    try:
        installer = Installer()
        distro_id = args.distro if args.distro else installer.get_distro()
        handler = installer.get_pkg_handler(distro_id)

        msg = ""
        if args.build:
            pkgs = handler.get_build_pkgs(args.m32)
            msg += " ".join(pkgs)
            pkgs = handler.get_libs_pkgs(args.m32)
            msg += " ".join(pkgs)

        if args.runtime:
            pkgs = handler.get_runtime_pkgs(args.m32)
            msg += " ".join(pkgs)

        print(msg)
    except InstallerError as err:
        print(str(err))


def main():
    """
    Main point for the install script.
    """
    parser = argparse.ArgumentParser(description='LTP packages')
    parser.add_argument(
        "--distro",
        metavar="DISTRO_ID",
        type=str,
        default="",
        help="Linux distribution name in the /etc/os-release ID format")
    parser.add_argument(
        "--m32",
        action="store_true",
        help="Show 32 bits packages")
    parser.add_argument(
        "--build",
        action="store_true",
        help="Include build packages")
    parser.add_argument(
        "--runtime",
        action="store_true",
        help="Include runtime packages")
    parser.add_argument(
        "--cmd",
        action="store_true",
        help="Print command line instead of package list")

    args = parser.parse_args()

    install_run(args)


if __name__ == "__main__":
    main()
