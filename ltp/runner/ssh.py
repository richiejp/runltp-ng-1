"""
.. module:: ssh
    :platform: Linux
    :synopsis: SSH Runner implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ltp.common.ssh import SSH
from ltp.common.ssh import SSHError
from .base import Runner
from .base import RunnerError


class SSHRunner(SSH, Runner):
    """
    SSH Runner implementation class.
    """

    def start(self) -> None:
        try:
            self.connect()
        except SSHError as err:
            raise RunnerError(err)

    def stop(self) -> None:
        try:
            self.disconnect()
        except SSHError as err:
            raise RunnerError(err)

    def force_stop(self) -> None:
        self.stop()

    def run_cmd(self,
                command: str,
                timeout: int = 3600,
                cwd: str = None,
                env: dict = None,
                stdout_callback: callable = None) -> dict:
        try:
            ret = self.execute(
                command,
                timeout=timeout,
                cwd=cwd,
                env=env,
                stdout_callback=stdout_callback)
        except SSHError as err:
            raise RunnerError(err)

        return ret
