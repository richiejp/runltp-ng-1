"""
.. module:: qemu
    :platform: Linux
    :synopsis: module defining qemu backend

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import time
import shutil
import logging
import subprocess
from typing import Any
from ltp.downloader import TransportDownloader
from ltp.runner import SerialRunner
from .base import Backend
from .base import BackendError
from .base import BackendFactory

# pylint: disable=too-many-instance-attributes
# pylint: disable=consider-using-with


class QemuBackend(Backend):
    """
    Qemu backend spawn a new VM using qemu and execute commands inside it.
    This Backend implementation can be used to run LTP testing suites inside
    a protected, virtualized environment.
    """

    def __init__(self, **kwargs) -> None:
        self._ltpdir = kwargs.get("ltpdir", "/opt/ltp")
        self._tmpdir = kwargs.get("tmpdir", None)
        self._image = kwargs.get("image", None)
        self._image_overlay = kwargs.get("image_overlay", None)
        self._ro_image = kwargs.get("ro_image", None)
        self._password = kwargs.get("password", "root")
        self._opts = kwargs.get("options", None)
        self._ram = kwargs.get("ram", "2G")
        self._smp = kwargs.get("smp", "2")
        self._virtfs = kwargs.get("virtfs", "/mnt")
        self._serial = kwargs.get("serial", "isa")
        self._logger = logging.getLogger("ltp.backend.qemu")
        self._proc = None
        self._runner = None
        self._downloader = None

        system = kwargs.get("system", "x86_64")
        self._qemu_cmd = f"qemu-system-{system}"

        if not self._tmpdir or not os.path.isdir(self._tmpdir):
            raise ValueError("temporary directory doesn't exist")

        if not self._image or not os.path.isfile(self._image):
            raise ValueError("Image location doesn't exist")

        if self._ro_image and not os.path.isfile(self._ro_image):
            raise ValueError("Read-only image location doesn't exist")

        if not self._ram:
            raise ValueError("RAM is not defined")

        if not self._smp:
            raise ValueError("CPU is not defined")

        if not self._virtfs or not os.path.isdir(self._virtfs):
            raise ValueError("Virtual FS directory doesn't exist")

        if self._serial not in ["isa", "virtio"]:
            raise ValueError("Serial protocol must be isa or virtio")

        self._qemu_tmp = os.path.join(self._tmpdir, "qemu")
        if not os.path.exists(self._qemu_tmp):
            os.mkdir(self._qemu_tmp)

    def _vm_wait_and_send(self, towait: Any, tosend: str) -> None:
        """
        Wait for a string and send a reply.
        """
        line = ""

        while not self._proc.poll():
            data = self._proc.stdout.read(1)
            if not data:
                continue

            line += data

            if line.endswith(towait):
                self._proc.stdin.write(tosend)
                self._proc.stdin.write("\n")
                self._proc.stdin.flush()
                break

            if data == '\n':
                self._logger.info(line.rstrip())
                line = ""

        exitcode = self._proc.poll()
        if exitcode and exitcode != 0:
            raise BackendError(
                f"Qemu session ended with exit code {exitcode}")

    def stop(self) -> None:
        if not self._proc:
            return

        self._logger.info("Shutting down virtual machine")

        self._proc.stdin.write("poweroff")
        self._proc.stdin.write("\n")
        self._proc.stdin.flush()

        start_t = time.time()
        while self._proc.poll() is None:
            time.sleep(0.2)
            if time.time() - start_t >= 30:
                raise BackendError("Virtual machine timed out during poweroff")

        self._logger.info("Virtual machine stopped")

    def force_stop(self) -> None:
        if not self._proc:
            return

        self._logger.info("Killing virtual machine")

        self._proc.kill()

        self._logger.info("Virtual machine killed")

    # pylint: disable=too-many-statements
    def communicate(self) -> set:
        if self._proc:
            raise BackendError("Virtual machine is already running")

        if not shutil.which(self._qemu_cmd):
            raise BackendError(f"Command not found: {self._qemu_cmd}")

        self._logger.info("Starting virtual machine")

        pid = os.getpid()
        tty_log = os.path.join(self._qemu_tmp, f"ttyS0-{pid}.log")
        transport_file = os.path.join(self._qemu_tmp, f"transport-{pid}")
        transport_dev = ""

        image = self._image
        if self._image_overlay:
            shutil.copyfile(
                self._image,
                self._image_overlay)
            image = self._image_overlay

        params = []
        params.append("-enable-kvm")
        params.append("-display none")
        params.append(f"-m {self._ram}")
        params.append(f"-smp {self._smp}")
        params.append("-device virtio-rng-pci")
        params.append(f"-drive if=virtio,cache=unsafe,file={image}")
        params.append(f"-chardev stdio,id=tty,logfile={tty_log}")

        if self._serial == "isa":
            transport_dev = "ttyS1"
            params.append("-serial chardev:tty")
            params.append("-serial chardev:transport")
        elif self._serial == "virtio":
            transport_dev = "vport1p1"
            params.append("-device virtio-serial")
            params.append("-device virtconsole,chardev=tty")
            params.append("-device virtserialport,chardev=transport")
        else:
            raise NotImplementedError(
                f"Unsupported serial device type {self._serial}")

        params.append(f"-chardev file,id=transport,path={transport_file}")

        if self._ro_image:
            params.append(
                "-drive read-only,"
                "if=virtio,"
                "cache=unsafe,"
                f"file={self._ro_image}")

        if self._virtfs:
            params.append(
                "-virtfs local,"
                f"path={self._virtfs},"
                "mount_tag=host0,"
                "security_model=mapped-xattr,"
                "readonly=on")

        if self._opts:
            params.extend(self._opts)

        cmd = f"{self._qemu_cmd} {' '.join(params)}"

        self._logger.debug(cmd)

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            universal_newlines=True)

        self._vm_wait_and_send("login:", "root")
        self._vm_wait_and_send(("Password:", "password:"), self._password)
        self._vm_wait_and_send("#", "\n")

        self._logger.info("Creating communication objects")

        self._runner = SerialRunner(self._proc.stdout, self._proc.stdin)
        self._downloader = TransportDownloader(
            self._runner,
            transport_dev,
            transport_file)

        self._logger.info("Exporting LTP variables")

        testcases = os.path.join(self._ltpdir, "testcases", "bin")
        colors = os.environ.get("LTP_COLORIZE_OUTPUT", "y")

        # TODO: handle TMPDIR?
        self._runner.run_cmd("export PS1=''", 1)
        self._runner.run_cmd(f"export PATH=$PATH:{testcases}", 1)
        self._runner.run_cmd(f"export LTPROOT={self._ltpdir}", 1)
        self._runner.run_cmd(f"export LTP_COLORIZE_OUTPUT={colors}", 1)
        self._runner.run_cmd("cd $LTPROOT", 1)

        self._logger.info("Virtual machine started")

        return self._downloader, self._runner


class QemuBackendFactory(BackendFactory):
    """
    Factory class implementation for QemuBackend.
    """

    def __init__(self, **kwargs) -> None:
        """
        :param ltpdir: LTP install directory
        :type ltpdir: str
        :param tmpdir: Session temporary directory
        :type tmpdir: str
        :param image: Path to bootable qemu image
        :type image: str
        :param image_overlay: If set, an image overlay is created before each
            boot and changes are written to that instead of the original
        :type image: str
        :param password: Qemu image root password
        :type password: str
        :param opts: Additional qemu command line options
        :type opts: list(str)
        :param system: Qemu system, defaults to x86_64
        :type system: str
        :param ram: Qemu RAM size, defaults to 2G
        :type ram: str
        :param smp: Qemu CPUs defaults to 2
        :type smp: str
        :param virtfs: Path to a host folder to mount in the guest (on /mnt)
        :type virtfs: str
        :param serial: Qemu serial port device type, currently only support isa
            (default) and virtio
        :type serial: str
        :param ro_image: Path to an image which will be exposed as read only
        :type ro_image: str
        """
        self._kwargs = kwargs

    def create(self) -> Backend:
        return QemuBackend(**self._kwargs)
