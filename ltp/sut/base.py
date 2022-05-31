"""
.. module:: base
    :platform: Linux
    :synopsis: module containing SUT definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import time
from ltp import LTPException


class SUTError(LTPException):
    """
    Raised when an error occurs in SUT.
    """


class SUTTimeoutError(LTPException):
    """
    Raised when timeout error occurs in SUT.
    """


class SUT:
    """
    A SUT is the target where tests are executed. It could be a remote
    host, a local host, a virtual machine instance, etc.
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
                raise TimeoutError("Stop timed out after 30 seconds")

    @property
    def name(self) -> str:
        """
        Name of the SUT.
        """
        raise NotImplementedError()

    @property
    def is_running(self) -> bool:
        """
        Return True if object is running.
        """
        raise NotImplementedError()

    def communicate(self, stdout_callback: callable = None) -> None:
        """
        Start communicating with the SUT and it initialize internal
        communication objects such as runner and downloader.
        :param stdout_callback: callback that is called all the times a new
            line came out from stdout during SUT execution.
        :type stdout_callback: callable
        """
        raise NotImplementedError()

    def stop(self, timeout: int = 30) -> None:
        """
        Stop the current SUT session.
        :param timeout: timeout to complete in seconds
        :type timeout: int
        """
        raise NotImplementedError()

    def force_stop(self, timeout: int = 30) -> None:
        """
        Force stopping the current SUT session.
        :param timeout: timeout to complete in seconds
        :type timeout: int
        """
        raise NotImplementedError()

    def run_command(self,
                    command: str,
                    timeout: int = 3600,
                    cwd: str = None,
                    env: dict = None,
                    stdout_callback: callable = None) -> dict:
        """
        Run command on target.
        :param command: command to execute
        :param timeout: timeout before stopping execution. Default is 3600
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

    def fetch_file(
            self,
            target_path: str,
            local_path: str,
            timeout: int = 3600) -> None:
        """
        Fetch file from target path and download it in the specified
        local path.
        :param target_path: path of the file to download from target
        :type target_path: str
        :param local_path: path of the downloaded file on local host
        :type local_path: str
        :param timeout: timeout before stopping data transfer. Default is 3600
        :type timeout: int
        """
        raise NotImplementedError()
