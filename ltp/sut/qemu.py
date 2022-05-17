"""
.. module:: qemu
    :platform: Linux
    :synopsis: module defining qemu SUT

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import time
import shutil
import logging
import subprocess
import threading
from ltp.channel import SerialChannel
from ltp.channel import Channel
from ltp.common.freader import IOReader
from .base import SUT
from .base import SUTError

# pylint: disable=too-many-instance-attributes
# pylint: disable=consider-using-with


class QemuSUT(SUT):
    """
    Qemu SUT spawn a new VM using qemu and execute commands inside it.
    This SUT implementation can be used to run LTP testing suites inside
    a protected, virtualized environment.
    """

    def __init__(self, **kwargs) -> None:
        self._tmpdir = kwargs.get("tmpdir", None)
        self._image = kwargs.get("image", None)
        self._image_overlay = kwargs.get("image_overlay", None)
        self._ro_image = kwargs.get("ro_image", None)
        self._password = kwargs.get("password", "root")
        self._opts = kwargs.get("options", None)
        self._ram = kwargs.get("ram", "2G")
        self._smp = kwargs.get("smp", "2")
        self._virtfs = kwargs.get("virtfs", None)
        self._serial = kwargs.get("serial", "isa")
        self._logger = logging.getLogger("ltp.sut.qemu")
        self._proc = None
        self._reader = None
        self._stdout = None
        self._stdin = None
        self._channel = None
        self._stop = False
        self._logged = False
        self._lock = threading.Lock()

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

        if self._virtfs and not os.path.isdir(self._virtfs):
            raise ValueError("Virtual FS directory doesn't exist")

        if self._serial not in ["isa", "virtio"]:
            raise ValueError("Serial protocol must be isa or virtio")

    @property
    def name(self) -> str:
        return "qemu"

    @property
    def channel(self) -> Channel:
        return self._channel

    def stop(self, timeout: int = 30) -> None:
        with self._lock:
            self._stop = True

            if self._channel:
                self._channel.stop()
                self._channel = None

            if self._proc:
                self._logger.info("Shutting down virtual machine")

                self._reader.stop()
                self._reader = None

                if self._logged:
                    self._proc.stdin.write("poweroff\n")

                    try:
                        self._proc.stdin.flush()
                    except BrokenPipeError:
                        # sometimes we need to flush data after poweroff is
                        # sent, but if poweroff already shutted down VM, we'll
                        # obtain a BrokenPipeError that has to be ignored in
                        # this case
                        pass
                else:
                    self._proc.terminate()

                secs = max(timeout, 0)
                start_t = time.time()

                while self._proc.poll() is None:
                    time.sleep(0.05)
                    if time.time() - start_t > secs:
                        raise SUTError(
                            "Virtual machine timed out during poweroff")

                self._proc = None

                self._logger.info("Virtual machine stopped")

    def force_stop(self, timeout: int = 30) -> None:
        with self._lock:
            self._stop = True

            if self._channel:
                self._channel.force_stop(timeout=timeout)
                self._channel = None

            self._reader.stop()
            self._reader = None

            if self._proc:
                self._logger.info("Killing virtual machine")
                self._proc.kill()

                secs = max(timeout, 0)
                start_t = time.time()

                while self._proc.poll() is None:
                    time.sleep(0.05)
                    if time.time() - start_t > secs:
                        raise SUTError("Virtual machine timed out during kill")

                self._proc = None

                self._logger.info("Virtual machine killed")

    # pylint: disable=too-many-statements
    def communicate(self, stdout_callback: callable = None) -> None:
        if self._proc:
            raise SUTError("Virtual machine is already running")

        if not shutil.which(self._qemu_cmd):
            raise SUTError(f"Command not found: {self._qemu_cmd}")

        self._stop = False
        self._logged = False

        self._logger.info("Starting virtual machine")

        pid = os.getpid()
        tty_log = os.path.join(self._tmpdir, f"ttyS0-{pid}.log")
        transport_file = os.path.join(self._tmpdir, f"transport-{pid}")
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

        exitcode = self._proc.poll()
        if exitcode and exitcode != 0:
            if not self._stop:
                raise SUTError(f"Qemu session ended with exit code {exitcode}")

        if self._stop:
            return

        self._reader = IOReader(self._proc.stdout.fileno())

        self._logger.info("Waiting for login message")

        self._reader.read_until(
            lambda x: x.endswith("login:"),
            time.time(),
            180,
            stdout_callback)

        if self._reader and self._reader.timed_out:
            raise SUTError("Can't find login message")

        if self._stop:
            return

        self._proc.stdin.write("root")
        self._proc.stdin.write("\n")
        self._proc.stdin.flush()

        self._logger.info("Waiting for password message")

        self._reader.read_until(
            lambda x: x.endswith(("Password:", "password:")),
            time.time(),
            30,
            stdout_callback)

        if self._reader and self._reader.timed_out:
            raise SUTError("Can't find password message")

        if self._stop:
            return

        self._logger.info("Logged in")

        self._proc.stdin.write(self._password)
        self._proc.stdin.write("\n")
        self._proc.stdin.flush()

        self._reader.read_until(
            lambda x: x.endswith("#"),
            time.time(),
            30,
            stdout_callback)

        if self._reader and self._reader.timed_out:
            raise SUTError("Can't find prompt shell")

        if self._stop:
            return

        self._proc.stdin.write("\n")
        self._proc.stdin.flush()

        self._logged = True

        if self._stop:
            return

        self._logger.info("Creating communication objects")

        self._channel = SerialChannel(
            stdin=self._proc.stdin,
            stdout=self._proc.stdout,
            transport_dev=f"/dev/{transport_dev}",
            transport_path=transport_file)

        self._channel.start()

        if self._stop:
            return

        if self._virtfs:
            self._channel.run_cmd("mount -t 9p -o trans=virtio host0 /mnt")

        self._logger.info("Virtual machine started")
