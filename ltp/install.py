"""
.. module:: install
    :platform: Linux
    :synopsis: module that contains LTP installer definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import time
import logging
import subprocess
from argparse import ArgumentParser
from argparse import Namespace


class InstallerError(Exception):
    """
    Raised when an error occurs during LTP install.
    """


class Installer:
    """
    A generic LTP installer that should be inherited to create a specific
    distro LTP installer.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("ltp.installer")
        self._logger.debug("initialized installer for %s", self.distro_id)
        self._proc = None
        self._stop = False

    @property
    def distro_id(self) -> str:
        """
        Name of the distro.
        """
        raise NotImplementedError()

    def setup_32bit(self) -> None:
        """
        Override this method if distro must be configured for
        32bit installation.
        """

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

    def get_tools_pkgs(self) -> list:
        """
        Return tools libraries packages.
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

    def stop(self):
        """
        Stop any install operation.
        """
        if not self._proc:
            return

        self._logger.info("Stopping installer")

        self._stop = True
        while self._stop:
            time.sleep(0.2)

        self._logger.info("Installer stopped")

    def _run_cmd(
            self,
            cmd: str,
            cwd: str = None,
            raise_err: bool = True,
            stdout_callback: callable = None) -> None:
        """
        Run a command inside the shell
        """
        self._logger.info("Running command '%s'", cmd)

        self._stop = False

        # pylint: disable=consider-using-with
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            shell=True,
            universal_newlines=True)

        try:
            while self._proc.poll() is None:
                if self._stop:
                    break

                line = self._proc.stdout.readline()
                if not line:
                    break

                self._logger.info(line.rstrip())

                if stdout_callback:
                    stdout_callback(line.rstrip())

            self._proc.wait()

            if raise_err and self._proc.returncode != 0:
                raise InstallerError(
                    f"'{cmd}' return code: {self._proc.returncode}")
        finally:
            self._proc.terminate()
            self._proc = None
            self._stop = False

    def clone_repo(
            self,
            url: str,
            repo_dir: str,
            stdout_callback: callable = None) -> None:
        """
        Run LTP installation from Git repository.
        """
        self._logger.info("Cloning repository..")
        self._run_cmd(
            f"git clone --depth=1 {url} {repo_dir}",
            stdout_callback=stdout_callback)
        self._logger.info("Cloning completed")

    def install_from_src(
            self,
            repo_dir: str,
            install_dir: str,
            stdout_callback: callable = None) -> None:
        """
        Run LTP installation from Git repository.
        """
        self._logger.info("Compiling sources")

        cpus = subprocess.check_output(
            ['getconf', '_NPROCESSORS_ONLN']).rstrip().decode("utf-8")

        self._run_cmd(
            "make autotools",
            cwd=repo_dir,
            stdout_callback=stdout_callback)
        self._run_cmd(
            "./configure --prefix=" + install_dir,
            cwd=repo_dir,
            stdout_callback=stdout_callback)
        self._run_cmd(
            f"make -j{cpus}",
            cwd=repo_dir,
            stdout_callback=stdout_callback)
        self._run_cmd("make install", repo_dir)

        self._logger.info("Compiling completed")

    def install_requirements(
            self,
            m32_support: bool,
            stdout_callback: callable = None) -> None:
        """
        Install requirements for LTP installation according with Linux distro.
        """
        self._logger.info("Installing requirements")

        if m32_support:
            self.setup_32bit()

        pkgs = []

        pkgs.extend(self.get_build_pkgs(m32_support))
        pkgs.extend(self.get_runtime_pkgs(m32_support))
        pkgs.extend(self.get_libs_pkgs(m32_support))
        pkgs.extend(self.get_tools_pkgs())

        self._run_cmd(
            self.refresh_cmd,
            raise_err=False,
            stdout_callback=stdout_callback)
        self._run_cmd(
            f"{self.install_cmd} {' '.join(pkgs)}",
            stdout_callback=stdout_callback)

        self._logger.info("Installation completed")

    def install(self,
                m32_support: bool,
                url: str,
                repo_dir: str,
                install_dir: str,
                stdout_callback: callable = None) -> None:
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
        :param stdout_callback: callback called all the times a new line comes
            arrives in the stdout
        :type stdout_callback: callable
        :raises: InstallerError
        """
        if not url:
            raise ValueError("url is empty")

        if not repo_dir:
            raise ValueError("repo_dir is empty")

        if not install_dir:
            raise ValueError("install_dir is empty")

        self.install_requirements(
            m32_support,
            stdout_callback=stdout_callback)
        self.clone_repo(
            url,
            repo_dir,
            stdout_callback=stdout_callback)
        self.install_from_src(
            repo_dir,
            install_dir,
            stdout_callback=stdout_callback)


class OpenSUSEInstaller(Installer):
    """
    Installer for openSUSE.
    """

    @property
    def distro_id(self) -> str:
        return "opensuse"

    def get_build_pkgs(self, _: bool) -> list:
        return [
            "autoconf",
            "automake",
            "gcc",
            "git",
            "kernel-devel",
            "make",
            "pkg-config",
            "unzip",
        ]

    def get_runtime_pkgs(self, _: bool) -> list:
        return [
            "bc",
            "btrfsprogs",
            "dosfstools",
            "e2fsprogs",
            "nfs-kernel-server",
            "quota",
            "xfsprogs",
        ]

    def get_libs_pkgs(self, m32: bool) -> list:
        pkgs = None
        if m32:
            pkgs = [
                "libacl-devel-32bit",
                "libaio-devel-32bit",
                "libattr-devel-32bit",
            ]
        else:
            pkgs = [
                "libacl-devel",
                "libaio-devel",
                "libattr-devel",
                "libcap-devel",
                "libnuma-devel",
            ]

        return pkgs

    def get_tools_pkgs(self) -> list:
        return [
            "libssh4"
        ]

    @property
    def refresh_cmd(self) -> str:
        return "zypper --non-interactive refresh"

    @property
    def install_cmd(self) -> str:
        return "zypper --non-interactive --ignore-unknown install"


class SLESInstaller(OpenSUSEInstaller):
    """
    Installer for SLES.
    """

    @property
    def distro_id(self) -> str:
        return "sles"


class DebianInstaller(Installer):
    """
    Installer for Debian.
    """

    @property
    def distro_id(self) -> str:
        return "debian"

    def setup_32bit(self) -> None:
        self._logger.info("adding i386 architecture support")

        proc = subprocess.run(
            ['dpkg', '--add-architecture', 'i386'], check=True)
        if proc.returncode != 0:
            raise InstallerError("Can't add i386 support on debian")

    def get_build_pkgs(self, m32: bool) -> list:
        pkgs = [
            "automake",
            "autoconf",
            "git",
            "make",
            "pkg-config",
            "unzip",
        ]

        if m32:
            pkgs.append("gcc-multilib")
        else:
            pkgs.append("gcc")

        return pkgs

    def get_runtime_pkgs(self, _: bool) -> list:
        pkgs = [
            "bc",
            "btrfs-progs",
            "dosfstools",
            "e2fsprogs",
            "nfs-kernel-server",
            "quota",
            "xfsprogs",
        ]

        arch = subprocess.check_output(
            ['dpkg', '--print-architecture']).rstrip().decode("utf-8")
        pkgs.append(f"linux-headers-{arch}")

        return pkgs

    def get_libs_pkgs(self, m32: bool) -> list:
        pkgs = [
            "libacl1-dev",
            "libaio-dev",
            "libattr1-dev",
            "libcap-dev",
            "libnuma-dev",
        ]

        if m32:
            pkgs = [pkg + ":i386" for pkg in pkgs]

        return pkgs

    def get_tools_pkgs(self) -> list:
        return [
            "libssh-4"
        ]

    @property
    def refresh_cmd(self) -> str:
        return "apt-get -y update"

    @property
    def install_cmd(self) -> str:
        cmd = "DEBIAN_FRONTEND=noninteractive "
        cmd += "apt-get -y --no-install-recommends install"
        return cmd


class UbuntuInstaller(DebianInstaller):
    """
    Installer for Ubuntu.
    """

    @property
    def distro_id(self) -> str:
        return "ubuntu"

    def get_runtime_pkgs(self, _: bool) -> list:
        return [
            "bc",
            "btrfs-progs",
            "dosfstools",
            "e2fsprogs",
            "linux-headers-generic",
            "nfs-kernel-server",
            "quota",
            "xfsprogs",
        ]


class AlpineInstaller(Installer):
    """
    Installer for Alpine Linux.
    """

    @property
    def distro_id(self) -> str:
        return "alpine"

    def get_build_pkgs(self, _: bool) -> list:
        return [
            "autoconf",
            "automake",
            "build-base",
            "git",
            "linux-headers",
            "make",
            "pkgconf",
            "unzip",
        ]

    def get_runtime_pkgs(self, _: bool) -> list:
        return [
            "bc",
            "btrfs-progs",
            "dosfstools",
            "e2fsprogs",
            "nfs-utils",
            "quota-tools",
            "xfsprogs",
        ]

    def get_libs_pkgs(self, m32: bool) -> list:
        if m32:
            raise InstallerError("Alpine doesn't support 32bit")

        return [
            "acl-dev",
            "attr-dev",
            "libaio-dev",
            "libcap-dev",
            "numactl-dev",
        ]

    def get_tools_pkgs(self) -> list:
        return [
            "libssh"
        ]

    @property
    def refresh_cmd(self) -> str:
        return "apk update"

    @property
    def install_cmd(self) -> str:
        return "apk add"


class FedoraInstaller(Installer):
    """
    Installer for Fedora.
    """

    @property
    def distro_id(self) -> str:
        return "fedora"

    def get_build_pkgs(self, _: bool) -> list:
        return [
            "autoconf",
            "automake",
            "gcc",
            "git",
            "kernel-devel",
            "make",
            "pkg-config",
            "unzip",
        ]

    def get_runtime_pkgs(self, _: bool) -> list:
        return [
            "bc",
            "btrfs-progs",
            "dosfstools",
            "e2fsprogs",
            "nfs-utils",
            "quota",
            "xfsprogs",
        ]

    def get_libs_pkgs(self, m32: bool) -> list:
        pkgs = [
            "libacl-devel",
            "libaio-devel",
            "libattr-devel",
            "libcap-devel",
            "numactl-libs"
        ]

        if m32:
            pkgs = [pkg + ".i686" for pkg in pkgs]

        return pkgs

    def get_tools_pkgs(self) -> list:
        return [
            "libssh"
        ]

    @property
    def refresh_cmd(self) -> str:
        return "yum update -y"

    @property
    def install_cmd(self) -> str:
        return "yum install -y"


INSTALLERS = [
    OpenSUSEInstaller(),
    SLESInstaller(),
    DebianInstaller(),
    UbuntuInstaller(),
    AlpineInstaller(),
    FedoraInstaller(),
]


def get_distro() -> str:
    """
    Return the current distro name.
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

    return name


def get_installer(distro_id: str = None) -> Installer:
    """
    Return the proper installer according with distro ID. If distro ID is None,
    the installer for current distro will be returned.
    :param distro_id: name of the distro
    :type distro_id: str
    """
    handler = None
    distro = distro_id

    if not distro:
        distro = get_distro()

    for item in INSTALLERS:
        if item.distro_id in distro:
            handler = item
            break

    if not handler:
        raise InstallerError(f"{distro} is not supported")

    return handler


def install_run(args: Namespace) -> None:
    """
    Run the installer main command.
    """
    if not args.build and not args.runtime and not args.tools:
        print("No packages selected!")
        return

    try:
        distro_id = args.distro if args.distro else None
        installer = get_installer(distro_id)

        msg = ""
        if args.cmd:
            msg += installer.refresh_cmd
            msg += " && "
            msg += installer.install_cmd
            msg += " "

        if args.build:
            pkgs = installer.get_build_pkgs(args.m32)
            msg += " ".join(pkgs)
            pkgs = installer.get_libs_pkgs(args.m32)
            msg += " ".join(pkgs)

        if args.runtime:
            pkgs = installer.get_runtime_pkgs(args.m32)
            msg += " ".join(pkgs)

        if args.tools:
            pkgs = installer.get_tools_pkgs()
            msg += " ".join(pkgs)

        print(msg)
    except InstallerError as err:
        print(str(err))


def init_cmdline(parser: ArgumentParser, callback: callable) -> None:
    """
    Initialize command line arguments.
    """
    parser.set_defaults(func=callback)
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
        "--tools",
        action="store_true",
        help="Include tools packages")
    parser.add_argument(
        "--cmd",
        action="store_true",
        help="Print command line instead of package list")


def main():
    """
    Main point for the install script.
    """
    parser = ArgumentParser(description='LTP packages tool')
    init_cmdline(parser, install_run)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
