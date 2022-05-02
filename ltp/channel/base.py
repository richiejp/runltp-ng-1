"""
.. module:: base
    :platform: Linux
    :synopsis: module containing Channel definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import time
from ltp import LTPException


class ChannelError(LTPException):
    """
    Raised when an error occurs inside Channel implementation.
    """


class Channel:
    """
    Channel permits to execute commands on target and to transfer data between
    host and target.
    """

    def _wait_for_stop(self, timeout: int = 30):
        """
        Helper method that can be used after having stopped command run or data
        transfer. This method will raise an exception after an amount of time
        if command or data transfer didn't stop.
        """
        secs = max(timeout, 0)
        start_t = time.time()

        while self.is_running:
            if time.time() - start_t > secs:
                raise ChannelError("Stop timed out after 30 seconds")

    @property
    def is_running(self) -> bool:
        """
        Return True if object is running.
        """
        raise NotImplementedError()

    def start(self) -> None:
        """
        Connect to channel.
        """
        raise NotImplementedError()

    def stop(self, timeout: int = 30) -> None:
        """
        Disconnect from channel.
        :param timeout: timeout to complete in seconds
        :type timeout: int
        """
        raise NotImplementedError()

    def force_stop(self, timeout: int = 30) -> None:
        """
        Forcly stop the channel.
        :param timeout: timeout to complete in seconds
        :type timeout: int
        """
        raise NotImplementedError()

    def run_cmd(self,
                command: str,
                timeout: int = 3600,
                cwd: str = None,
                env: dict = None,
                stdout_callback: callable = None) -> dict:
        """
        Run a command on target.
        :param command: command to execute
        :param timeout: seconds before raising an exception. If 0, no timeout
            will be applied. Default is 3600.
        :type timeout: int
        :param cwd: current working directory
        :type cwd: str
        :param env: environment variables
        :type env: dict
        :param stdout_callback: callback that can be used to get stdout lines
            in realtime.
        :type stdout_callback: callable
        :returns: dictionary containing command execution information

            {
                "command": <str>,
                "timeout": <int>,
                "returncode": <int>,
                "stdout": <str>,
                "exec_time": <int>,
                "cwd": <str>,
                "env": <dict>,
            }

            If None is returned, then callback failed.
        """
        raise NotImplementedError()

    def fetch_file(self, target_path: str, local_path: str) -> None:
        """
        Fetch file from target path and download it in the specified
        local path.
        :param target_path: path of the file to download from target
        :type target_path: str
        :param local_path: path of the downloaded file on local host
        :type local_path: str
        """
        raise NotImplementedError()
