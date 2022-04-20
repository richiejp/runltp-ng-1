"""
.. module:: base
    :platform: Linux
    :synopsis: module containing Runner definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ltp import LTPException


class RunnerError(LTPException):
    """
    Raised when an error occurs inside Runner.
    """


class Runner:
    """
    Runner permits to execute commands on target using a specific protocol.
    """

    def start(self) -> None:
        """
        Start runner.
        """
        raise NotImplementedError()

    def stop(self) -> None:
        """
        Stop Runner.
        """
        raise NotImplementedError()

    def force_stop(self) -> None:
        """
        Forcly stop the Runner.
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
