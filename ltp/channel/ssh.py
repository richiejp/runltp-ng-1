"""
.. module:: ssh
    :platform: Linux
    :synopsis: SSH channel implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import time
import logging
import socket
from threading import Timer
from .base import Channel
from .base import ChannelError
from .base import ChannelTimeoutError

try:
    from paramiko import SSHClient
    from paramiko import AutoAddPolicy
    from paramiko import SSHException
    from paramiko import RSAKey
    from scp import SCPClient
    from scp import SCPException
except ModuleNotFoundError:
    pass


class SSHBase:
    """
    Base class for each class using SSH.
    """

    def __init__(self, **kwargs) -> None:
        """
        :param host: TCP address
        :type host: str
        :param port: TCP port
        :type port: int
        :param user: username for logging in
        :type user: str
        :param password: password for logging in
        :type password: str
        :param timeout: connection timeout
        :type timeout: int
        :param key_file: file of the SSH keys
        :type key_file: str
        :param ssh_opts: additional SSH options
        :type ssh_opts: str
        """
        self._logger = logging.getLogger("ltp.ssh")
        self._host = kwargs.get("host", "localhost")
        self._port = int(kwargs.get("port", "22"))
        self._user = kwargs.get("user", "root")
        self._timeout = int(kwargs.get("timeout", "10"))
        self._password = kwargs.get("password", None)
        self._key_file = kwargs.get("key_file", None)
        self._ssh_opts = kwargs.get("ssh_opts", None)

        try:
            self._client = SSHClient()
        except NameError:
            self._client = None

        if not self._host:
            raise ValueError("host is empty")

        if not self._user:
            raise ValueError("user is empty")

        if self._port <= 0 or self._port >= 65536:
            raise ValueError("port is out of range")

        if self._key_file and not os.path.isfile(self._key_file):
            raise ValueError("private key doesn't exist")


class SSHChannel(SSHBase, Channel):
    """
    SSH channel connect via SSH protocol and execute/transfer data between
    target and host.
    """

    def __init__(self, **kwargs) -> None:
        """
        :param host: TCP address
        :type host: str
        :param port: TCP port
        :type port: int
        :param user: username for logging in
        :type user: str
        :param password: password for logging in
        :type password: str
        :param timeout: connection timeout
        :type timeout: int
        :param key_file: file of the SSH keys
        :type key_file: str
        :param ssh_opts: additional SSH options
        :type ssh_opts: str
        """
        super().__init__(**kwargs)
        self._stop = False
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if not self._client:
            raise ChannelError("paramiko package is not installed")

        if self._client.get_transport():
            if self._client.get_transport().is_active():
                self._logger.info("Connection is already up")
                return

        try:
            self._logger.info("Loading system keys")
            self._client.load_system_host_keys()
            self._client.set_missing_host_key_policy(AutoAddPolicy())

            self._logger.info("Connecting to %s:%d", self._host, self._port)

            pkey = None
            if self._key_file:
                pkey = RSAKey.from_private_key_file(self._key_file)

            self._client.connect(
                self._host,
                port=self._port,
                username=self._user,
                password=self._password,
                pkey=pkey,
                timeout=self._timeout)

            self._logger.info("Connected to host")
        except SSHException as err:
            raise ChannelError(err)
        except socket.error as err:
            raise ChannelError(err)
        except ValueError as err:
            raise ChannelError(err)

    def stop(self, timeout: int = 30) -> None:
        try:
            self._logger.info("Closing connection")
            self._stop = True
            self._client.close()
            self._logger.info("Connection closed")
        except SSHException as err:
            raise ChannelError(err)

        self._wait_for_stop(timeout=timeout)

    def force_stop(self, timeout: int = 30) -> None:
        self.stop(timeout=timeout)

    # pylint: disable=too-many-locals
    def run_cmd(self,
                command: str,
                timeout: int = 3600,
                cwd: str = None,
                env: dict = None,
                stdout_callback: callable = None) -> dict:
        if not command:
            raise ValueError("command is empty")

        self._logger.info(
            "Executing command (timeout=%d): %s", timeout, command)

        t_secs = max(timeout, 0)
        t_start = time.time()
        t_end = 0
        retcode = -1
        stdout_str = ""

        try:
            cmd = ""
            if cwd:
                cmd = f"cd {cwd} && "

            # environment can't be set by exec_command, since it requires
            # a server side setup enabling AcceptEnv, so we apply them with
            # the command
            if env:
                for key, value in env.items():
                    cmd += f"export {key}={value} && "

            cmd += command

            _, stdout, _ = self._client.exec_command(
                cmd,
                timeout=t_secs)

            self._running = True

            while True:
                time.sleep(0.05)

                line = stdout.readline()
                if not line:
                    break

                if stdout_callback:
                    stdout_callback(line.rstrip())

                self._logger.info(line.rstrip())
                stdout_str += line

            t_end = time.time() - t_start
            retcode = stdout.channel.recv_exit_status()
        except SSHException as err:
            if "Timeout" in str(err):
                raise ChannelTimeoutError(
                    f"'{command}' command timed out (timeout={timeout})")
            else:
                raise ChannelError(err)
        except socket.timeout as err:
            raise ChannelTimeoutError(
                f"'{command}' command timed out (timeout={timeout})")
        except FileNotFoundError as err:
            # key not found
            raise ChannelError(err)
        finally:
            self._running = False

        ret = {
            "command": command,
            "stdout": stdout_str,
            "returncode": retcode,
            "timeout": t_secs,
            "exec_time": t_end,
            "cwd": cwd,
            "env": env,
        }

        self._logger.debug("return data=%s", ret)
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

        self._stop = False

        self._logger.info("Transfer file: %s -> %s", target_path, local_path)

        def _threaded():
            self._logger.info("Command timed out after %d seconds", timeout)
            self.force_stop()

        secs_t = max(timeout, 0)
        timer = Timer(secs_t, _threaded)

        try:
            with SCPClient(self._client.get_transport()) as scp:
                self._running = True

                timer.start()

                scp.get(target_path, local_path=local_path)
        except (SCPException, SSHException, EOFError) as err:
            if not self._stop:
                raise ChannelError(err)
        except NameError:
            raise ChannelError("scp package is not installed")
        finally:
            self._stop = False
            self._running = False

            time.sleep(0.1)

            if timer.finished.is_set():
                raise ChannelTimeoutError(
                    f"Timeout during transfer (timeout={timeout}): "
                    f"{target_path} -> {local_path}")

            timer.cancel()

        self._logger.info("File transfer completed")
