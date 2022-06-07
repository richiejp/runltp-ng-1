"""
.. module:: qemu
    :platform: Linux
    :synopsis: module defining a generic qemu SUT

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import re
import time
import string
import signal
import shutil
import secrets
import logging
import subprocess
import threading
from ltp.common.freader import IOReader
from .base import SUT
from .base import SUTError
from .base import SUTTimeoutError

# pylint: disable=too-many-instance-attributes
# pylint: disable=consider-using-with


class VirtualMachine(SUT):
    """
    This SUT spawns a new VM using qemu and execute commands inside it.
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
        self._logger = logging.getLogger("ltp.sut.vm")
        self._proc = None
        self._reader = None
        self._stop = False
        self._logged = False
        self._stop_lock = threading.Lock()

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

    def stop(self, timeout: int = 30) -> None:
        with self._stop_lock:
            self._stop = True

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
        with self._stop_lock:
            self._stop = True

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

        if self._serial == "isa":
            transport_dev = "/dev/ttyS1"
        elif self._serial == "virtio":
            transport_dev = "/dev/vport1p1"

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

        if self._serial == "isa":
            params.append("-serial chardev:tty")
            params.append("-serial chardev:transport")
        elif self._serial == "virtio":
            params.append("-device virtio-serial")
            params.append("-device virtconsole,chardev=tty")
            params.append("-device virtserialport,chardev=transport")
        else:
            raise NotImplementedError(
                f"Unsupported serial device type {self._serial}")

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

        self._reader = IOReader(self._proc.stdout.fileno())

        self._logger.info("Waiting for login message")

        self._reader.read_until(
            lambda x: x.endswith(
                ("login:", "Is another process using the image")),
            time.time(),
            180,
            stdout_callback)

        exitcode = self._proc.poll()
        if exitcode and exitcode != 0:
            if not self._stop:
                raise SUTError(f"Qemu session ended with exit code {exitcode}")

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

    @property
    def is_running(self) -> bool:
        raise NotImplementedError()

    def run_command(self,
                    command: str,
                    timeout: int = 3600,
                    cwd: str = None,
                    env: dict = None,
                    stdout_callback: callable = None) -> dict:
        raise NotImplementedError()

    def fetch_file(
            self,
            target_path: str,
            local_path: str,
            timeout: int = 3600) -> None:
        raise NotImplementedError()


class QemuSUT(VirtualMachine):
    """
    This is not a standard serial I/O protocol communication class, but rather
    a helper class for sessions where a serial hw channel is exposed via file
    descriptor. This is really common in a qemu session, where console is
    exposed in the host system via file descriptor.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self._transport_dev, self._transport_path = self._get_transport()
        self._stop = False
        self._last_pos = 0
        self._initialized = False
        self._fetching_data = False
        self._running_command = False
        self._cmd_lock = threading.Lock()
        self._fetch_lock = threading.Lock()
        self._ps1 = f"#{self._generate_string()}#"

    @property
    def is_running(self) -> bool:
        return self._fetching_data or self._running_command

    def communicate(self, stdout_callback: callable = None) -> None:
        super().communicate(stdout_callback)

        if self._initialized or self._stop:
            return

        self._logger.info("Creating communication objects")

        self._init_prompt()
        self._initialized = True

        if self._stop:
            return

        if self._virtfs:
            self.run_command("mount -t 9p -o trans=virtio host0 /mnt")

        self._logger.info("Virtual machine started")

    def stop(self, timeout: int = 30) -> None:
        if self.is_running:
            with self._stop_lock:
                self._stop_running_command(timeout)
                self._stop_fetching_data(timeout)

        self._initialized = False

        super().stop(timeout)

    def force_stop(self, timeout: int = 30) -> None:
        self.stop(timeout=timeout)

    def _init_prompt(self) -> None:
        """
        Initialize shell prompt.
        """
        self._logger.info("Initializing command prompt")

        self._proc.stdin.write(f"export PS1='{self._ps1}'\n")
        self._proc.stdin.flush()

        self._wait_prompt(timeout=5)

    def _wait_prompt(self, timeout: int = 15) -> None:
        """
        Read stdout until prompt shows up.
        """
        self._logger.info("Waiting for command prompt")

        self._proc.stdin.write('\n')
        self._proc.stdin.flush()

        start_t = time.time()

        stdout = self._reader.read_until(
            lambda x: x.endswith(f"\n{self._ps1}"),
            start_t,
            timeout,
            self._logger.debug)

        if not stdout:
            if time.time() - start_t >= timeout:
                raise SUTTimeoutError("Prompt is not replying")

            raise SUTError("Prompt is not available")

    def _send_ctrl_c(self) -> None:
        """
        Send CTRL+C to stop any current command execution.
        """
        self._logger.info("Sending CTRL+C")
        self._proc.stdin.write('\x03')
        self._proc.stdin.flush()

    def _stop_running_command(self, timeout: int) -> None:
        """
        Stop the running command.
        """
        if not self._running_command:
            return

        self._logger.info("Stopping command")

        self._stop = True
        self._send_ctrl_c()
        self._wait_prompt(timeout=timeout)

        self._wait_for_stop(timeout=timeout)

        self._logger.info("Command stopped")

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

    @staticmethod
    def _generate_string(length: int = 10) -> str:
        """
        Generate a random string of the given length.
        """
        out = ''.join(secrets.choice(string.ascii_letters + string.digits)
                      for _ in range(length))
        return out

    def _send(self,
              cmd: str,
              timeout: int,
              stdout_callback: callable = None) -> set:
        """
        Send a command and return retcode, elabsed time and stdout.
        """
        code = self._generate_string()
        cmd_end = f"echo $?-{code}"
        matcher = re.compile(f"^(?P<retcode>\\d+)-{code}")

        stdout = ""
        retcode = -1
        t_start = time.time()
        t_secs = max(timeout, 0)
        t_end = 0

        self._proc.stdin.write(cmd)
        self._proc.stdin.write('\n')
        self._proc.stdin.write(cmd_end)
        self._proc.stdin.write('\n')
        self._proc.stdin.flush()

        while True:
            line = self._reader.read_until(
                lambda x: x.endswith('\n'),
                t_start,
                t_secs,
                self._logger.debug)

            if self._reader.timed_out:
                self._send_ctrl_c()
                self._wait_prompt(timeout=5)

                raise SUTTimeoutError(
                    f"'{cmd}' command timed out (timeout={timeout})")

            if self._stop:
                break

            # ignore echo
            if cmd in line or cmd_end in line:
                continue

            match = matcher.match(line)
            if match:
                retcode_str = match.group("retcode")
                self._logger.debug("rercode=%s", retcode_str)

                retcode = int(retcode_str)
                t_end = time.time() - t_start
                break

            if stdout_callback:
                stdout_callback(line.rstrip())

            stdout += line

        if self._stop:
            retcode = signal.SIGTERM

        t_end = time.time() - t_start

        return retcode, t_end, stdout

    def run_command(self,
                    command: str,
                    timeout: int = 3600,
                    cwd: str = None,
                    env: dict = None,
                    stdout_callback: callable = None) -> dict:
        if not command:
            raise ValueError("command is empty")

        ret = None

        with self._cmd_lock:
            self._logger.info("Running command: %s", command)
            self._stop = False

            t_secs = max(timeout, 0)
            retcode = -1
            t_end = 0
            stdout = ""

            cmd = ""
            if cwd:
                cmd = f"cd {cwd} && "

            if env:
                for key, value in env.items():
                    cmd += f"export {key}={value} && "

            cmd += command

            try:
                self._running_command = True

                retcode, t_end, stdout = self._send(
                    cmd, timeout, stdout_callback)

                ret = {
                    "command": command,
                    "timeout": t_secs,
                    "returncode": int(retcode),
                    "stdout": stdout,
                    "exec_time": t_end,
                    "env": env,
                    "cwd": cwd,
                }

                self._logger.debug(ret)
                self._logger.info("Command completed")
            except OSError as err:
                raise SUTError(err)
            finally:
                self._stop = False
                self._running_command = False

        return ret

    def fetch_file(
            self,
            target_path: str,
            local_path: str,
            timeout: int = 3600) -> None:
        if not target_path:
            raise ValueError("target path is empty")

        if not local_path:
            raise ValueError("local path is empty")

        with self._fetch_lock:
            self._logger.info("Downloading: %s -> %s", target_path, local_path)
            self._stop = False
            self._fetching_data = True

            try:
                ret = self.run_command(
                    f"cat {target_path} > {self._transport_dev}",
                    timeout=timeout)

                if ret["returncode"] not in [0, signal.SIGTERM]:
                    stdout = ret["stdout"]
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
