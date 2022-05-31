"""
.. module:: host
    :platform: Linux
    :synopsis: module containing host SUT declaration

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import time
import logging
import subprocess
import threading
from .base import SUT
from .base import SUTError
from .base import SUTTimeoutError


class HostSUT(SUT):
    """
    Shell Runner implementation class.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("ltp.sut.host")
        self._process = None
        self._running = False
        self._stop = False
        self._initialized = False

    @property
    def name(self) -> str:
        return "host"

    @property
    def is_running(self) -> bool:
        return self._running

    def communicate(self, stdout_callback: callable = None) -> None:
        if self._initialized:
            raise SUTError("SUT is running")

        self._initialized = True

    def stop(self, timeout: int = 30) -> None:
        self._initialized = False

        if not self.is_running:
            return

        self._stop = True

        if self._process:
            self._logger.info("Terminating process")
            self._process.terminate()
            self._logger.info("Process terminated")

        self._wait_for_stop(timeout=timeout)

    def force_stop(self, timeout: int = 30) -> None:
        if not self.is_running:
            return

        self._stop = True

        if self._process:
            self._logger.info("Killing process")
            self._process.kill()
            self._logger.info("Process killed")

        self._wait_for_stop(timeout=timeout)

    def run_command(self,
                    command: str,
                    timeout: int = 3600,
                    cwd: str = None,
                    env: dict = None,
                    stdout_callback: callable = None) -> dict:
        if self._process:
            self._logger.debug(
                "Process with pid=%d is already running",
                self._process.pid)

            raise SUTError("A command is already running")

        if not command:
            raise ValueError("command is empty")

        timeout = max(timeout, 0)

        self._logger.info(
            "Executing command (timeout=%d): %s", timeout, command)

        # keep usage of preexec_fn trivial
        # see warnings in https://docs.python.org/3/library/subprocess.html
        # pylint: disable=subprocess-popen-preexec-fn
        # pylint: disable=consider-using-with
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=env,
            shell=True,
            universal_newlines=True,
            preexec_fn=os.setsid)

        self._running = True

        ret = None
        timer = None
        t_start = time.time()
        t_end = 0

        try:
            stdout = ""
            t_secs = max(timeout, 0)

            if t_secs >= 0:
                def _threaded():
                    if self._stop:
                        return

                    self._logger.info(
                        "Command timed out after %d seconds", timeout)

                    if self._process:
                        self._process.kill()

                timer = threading.Timer(t_secs, _threaded)
                timer.start()

            while True:
                line = self._process.stdout.readline()
                if not line and self._process.poll() is not None:
                    t_end = time.time() - t_start
                    break

                if stdout_callback:
                    stdout_callback(line.rstrip())

                self._logger.info(line.rstrip())
                stdout += line

            ret = {
                "command": command,
                "stdout": stdout,
                "returncode": self._process.returncode,
                "timeout": t_secs,
                "exec_time": t_end,
                "cwd": cwd,
                "env": env,
            }
            self._logger.debug("return data=%s", ret)
        except subprocess.TimeoutExpired as err:
            self._process.kill()
            raise SUTError(err)
        finally:
            self._process = None
            self._running = False

            if timer:
                time.sleep(0.1)
                if timer.finished.is_set():
                    raise SUTTimeoutError(
                        f"'{command}' command timed out (timeout={timeout})")

                timer.cancel()

        self._logger.info("Command executed")

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

        if not os.path.isfile(target_path):
            raise ValueError("target file doesn't exist")

        self._logger.info("Copy '%s' to '%s'", target_path, local_path)

        self._stop = False

        try:
            start_t = time.time()

            with open(target_path, 'rb') as ftarget:
                with open(local_path, 'wb+') as flocal:
                    data = ftarget.read(1024)

                    self._running = True

                    while data != b'' and not self._stop:
                        flocal.write(data)
                        data = ftarget.read(1024)

                        if time.time() - start_t >= timeout:
                            self._logger.info(
                                "Transfer timed out after %d seconds", timeout)

                            raise SUTTimeoutError(
                                f"Timeout during transfer (timeout={timeout}):"
                                f" {target_path} -> {local_path}")
        except IOError as err:
            raise SUTError(err)
        finally:
            if self._stop:
                self._logger.info("Copy stopped")
                self._stop = False
            else:
                self._logger.info("File copied")

            self._running = False
