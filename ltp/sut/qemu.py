"""
.. module:: qemu
    :platform: Linux
    :synopsis: module defining qemu SUT

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import time
import signal
import shutil
import logging
import subprocess
import threading
from ltp.common.freader import IOReader
from .base import SUT
from .base import SUTError
from .base import SUTTimeoutError
from .prompt import CommandPrompt


class QemuSerial(CommandPrompt):
    """
    Serial class customization for Qemu SUT implementation.
    """

    def __init__(self, **kwargs) -> None:
        """
        :param transport_dev: transport device path
        :type transport_dev: str
        :param transport_path: transport file path
        :type transport_path: str
        """
        super().__init__(**kwargs)

        self._transport_dev = kwargs.get("transport_dev", None)
        self._transport_path = kwargs.get("transport_path", None)
        self._fetch_lock = threading.Lock()
        self._fetching_data = False

        if not self._transport_dev:
            raise ValueError("transport device is empty")

        if not self._transport_path or \
                not os.path.isfile(self._transport_path):
            raise ValueError("transport file doesn't exist")

    def _stop_fetching_data(self, timeout: int) -> None:
        """
        Stop fetching data.
        """
        if not self._fetching_data:
            return

        self._logger.info("Stop fetching data")

        self._stop = True
        self._wait_for_stop(timeout=timeout)

        self._logger.info("Fetching data stopped")

    @property
    def is_running(self) -> bool:
        return self._fetching_data or self._running_command

    def stop(self, timeout: int = 30) -> None:
        """
        Stop any operation on command prompt.
        """
        if not self.is_running:
            return

        with self._stop_lock:
            self._stop_running_command(timeout)
            self._stop_fetching_data(timeout)

    def get(
            self,
            target_path: str,
            local_path: str,
            timeout: int = 3600) -> None:
        """
        Get file from target path and download it in the specified local path.
        :param target_path: path of the file to download from target
        :type target_path: str
        :param local_path: path of the downloaded file on local host
        :type local_path: str
        :param timeout: timeout before stopping data transfer. Default is 3600
        :type timeout: int
        """
        if not target_path:
            raise ValueError("target path is empty")

        if not local_path:
            raise ValueError("local path is empty")

        with self._fetch_lock:
            self._logger.info("Downloading: %s -> %s", target_path, local_path)
            self._stop = False
            self._fetching_data = True

            try:
                retcode, _, stdout = self.execute(
                    f"cat {target_path} > {self._transport_dev}",
                    timeout=timeout)

                if retcode not in [0, signal.SIGTERM]:
                    raise SUTError(
                        f"Can't send file to {self._transport_dev}: {stdout}")

                if self._stop:
                    return

                # read back data and send it to the local file path
                file_size = os.path.getsize(self._transport_path)
                start_t = time.time()

                with open(self._transport_path, "rb") as transport:
                    with open(local_path, "wb") as flocal:
                        while not self._stop and self._last_pos < file_size:
                            if time.time() - start_t >= timeout:
                                self._logger.info(
                                    "Transfer timed out after %d seconds",
                                    timeout)

                                raise SUTTimeoutError(
                                    "Timeout during transfer "
                                    f"(timeout={timeout}):"
                                    f" {target_path} -> {local_path}")

                            time.sleep(0.05)

                            transport.seek(self._last_pos)
                            data = transport.read(4096)

                            self._last_pos = transport.tell()

                            flocal.write(data)

                self._logger.info("File downloaded")
            finally:
                self._stop = False
                self._fetching_data = False


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
        self._serial_type = kwargs.get("serial", "isa")
        self._logger = logging.getLogger("ltp.sut.qemu")
        self._proc = None
        self._reader = None
        self._stdout = None
        self._stdin = None
        self._serial = None
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

        if self._serial_type not in ["isa", "virtio"]:
            raise ValueError("Serial protocol must be isa or virtio")

    @property
    def name(self) -> str:
        return "qemu"

    @property
    def is_running(self) -> bool:
        return self._serial.is_running

    def stop(self, timeout: int = 30) -> None:
        with self._lock:
            self._stop = True

            if self._serial:
                self._serial.stop()
                self._serial = None

            if self._proc:
                self._logger.info("Shutting down virtual machine")

                if self._reader:
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

            if self._serial:
                self._serial.stop(timeout=timeout)
                self._serial = None

            if self._reader:
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

    def _get_transport(self) -> str:
        """
        Return a couple of transport_dev and transport_file used by
        qemu instance for transport configuration.
        """
        pid = os.getpid()
        transport_file = os.path.join(self._tmpdir, f"transport-{pid}")
        transport_dev = ""

        if self._serial_type == "isa":
            transport_dev = "ttyS1"
        elif self._serial_type == "virtio":
            transport_dev = "vport1p1"

        return transport_dev, transport_file

    def _get_command(self) -> str:
        """
        Return the full qemu command to execute.
        """
        pid = os.getpid()
        tty_log = os.path.join(self._tmpdir, f"ttyS0-{pid}.log")

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

        if self._serial_type == "isa":
            params.append("-serial chardev:tty")
            params.append("-serial chardev:transport")
        elif self._serial_type == "virtio":
            params.append("-device virtio-serial")
            params.append("-device virtconsole,chardev=tty")
            params.append("-device virtserialport,chardev=transport")
        else:
            raise NotImplementedError(
                f"Unsupported serial device type {self._serial_type}")

        _, transport_file = self._get_transport()
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

        return cmd

    # pylint: disable=too-many-statements
    def communicate(self, stdout_callback: callable = None) -> None:
        if self._proc:
            raise SUTError("Virtual machine is already running")

        if not shutil.which(self._qemu_cmd):
            raise SUTError(f"Command not found: {self._qemu_cmd}")

        self._stop = False
        self._logged = False

        self._logger.info("Starting virtual machine")

        cmd = self._get_command()

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

        self._logger.info("Creating communication object")

        transport_dev, transport_file = self._get_transport()

        self._serial = QemuSerial(
            stdin=self._proc.stdin,
            stdout=self._proc.stdout,
            transport_dev=f"/dev/{transport_dev}",
            transport_path=transport_file)

        self._serial.start()

        self._logged = True

        if self._stop:
            return

        if self._virtfs:
            retcode, _, _ = self._serial.execute(
                "mount -t 9p -o trans=virtio host0 /mnt")

            if retcode != 0:
                raise SUTError("Failed to mount virtfs")

        self._logger.info("Virtual machine started")

    def run_command(self,
                    command: str,
                    timeout: int = 3600,
                    cwd: str = None,
                    env: dict = None,
                    stdout_callback: callable = None) -> dict:
        if not self._serial:
            return None

        retcode, t_end, stdout = self._serial.execute(
            command,
            timeout=timeout,
            cwd=cwd,
            env=env,
            stdout_callback=stdout_callback)

        ret = {
            "command": command,
            "timeout": timeout,
            "returncode": retcode,
            "stdout": stdout,
            "exec_time": t_end,
            "cwd": cwd,
            "env": env,
        }

        return ret

    def fetch_file(self,
                   target_path: str,
                   local_path: str,
                   timeout: int = 3600) -> None:
        if not target_path:
            raise ValueError("target path is empty")

        if not local_path:
            raise ValueError("local path is empty")

        if self._serial:
            self._serial.get(
                target_path,
                local_path,
                timeout=timeout)
