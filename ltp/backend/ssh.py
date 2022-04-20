"""
.. module:: ssh
    :platform: Linux
    :synopsis: module defining SSH backend

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import logging
from ltp.common.ssh import SSH
from ltp.common.ssh import SSHBase
from ltp.downloader import Downloader
from ltp.runner import Runner
from .base import Backend
from .base import BackendError
from .base import BackendFactory


class SSHClient(Runner, Downloader, SSH):
    """
    Generic SSH client that is both runner and downloader.
    This is a choice made to keep a single connection for multiple
    implementations.
    """

    def start(self) -> None:
        self.connect()

    def stop(self, _: int = 0) -> None:
        self.disconnect()

    def force_stop(self) -> None:
        self.force_stop()

    def run_cmd(
            self,
            command: str,
            timeout: int = 3600,
            cwd: str = None,
            env: dict = None,
            stdout_callback: callable = None) -> dict:
        return self.execute(
            command,
            timeout=timeout,
            cwd=cwd,
            env=env,
            stdout_callback=stdout_callback)

    def fetch_file(self, target_path: str, local_path: str) -> None:
        self.get(target_path, local_path)


class SSHBackend(SSHBase, Backend):
    """
    A backend that is using SSH protocol con communicate and transfer data.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._logger = logging.getLogger("ltp.backend.ssh")
        self._ltpdir = kwargs.get("ltpdir", "/opt/ltp")
        self._tmpdir = kwargs.get("tmpdir", None)
        self._client = SSHClient(**kwargs)
        self._running = False

    @property
    def downloader(self) -> Downloader:
        return self._client

    @property
    def runner(self) -> Runner:
        return self._client

    def communicate(self) -> None:
        if self._running:
            raise BackendError("Backend is already running")

        self._client.start()
        self._running = True

    def stop(self) -> None:
        self._client.stop()

    def force_stop(self) -> None:
        self._client.force_stop()


class SSHBackendFactory(SSHBase, BackendFactory):
    """
    Factory object for SSHBackend implementation.
    """

    def create(self) -> Backend:
        backend = SSHBackend(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            timeout=self._timeout,
            key_file=self._key_file,
            ssh_opts=self._ssh_opts)

        return backend
