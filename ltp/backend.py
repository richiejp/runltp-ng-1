"""
.. module:: backend
    :platform: Linux
    :synopsis: module containing Backend definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""


class BackendError(Exception):
    """
    Raised when an error occurs.
    """


class Backend:
    """
    A generic backend that has to be inherited to implement a new backend.
    """

    @property
    def name(self) -> str:
        """
        Name of the backend.
        :returns: string naming the backend.
        """
        raise NotImplementedError()

    def start(self) -> None:
        """
        Start backend.
        """
        raise NotImplementedError()

    def stop(self, timeout: int = 0) -> None:
        """
        Stop backend.
        :param timeout: timeout before raising an exception. If 0, no timeout
            will be applied.
        :type timeout: int
        """
        raise NotImplementedError()

    def force_stop(self) -> None:
        """
        Forcly stop the backend.
        """
        raise NotImplementedError()

    def _run_cmd_impl(self, command: str, timeout: int) -> dict:
        """
        Run a command on target. This has to be implemented by the class that
        is inheriting Backend class.
        :param command: command to execute
        :param timeout: timeout before raising an exception. If 0, no timeout
            will be applied.
        :type timeout: int
        :returns: dictionary containing command execution information
            {
                "command": <mycommand>,
                "timeout": <timeout>,
                "returncode": <returncode>,
                "stdout": <stdout>,
            }
            If None is returned, then callback failed.
        """
        raise NotImplementedError()

    def run_cmd(self, command: str, timeout: int) -> dict:
        """
        Run a command on target.
        :param command: command to execute
        :param timeout: timeout before raising an exception. If 0, no timeout
            will be applied.
        :type timeout: int
        :returns: dictionary containing command execution information
            {
                "command": <mycommand>,
                "timeout": <timeout>,
                "returncode": <returncode>,
                "stdout": <stdout>,
            }
            If None is returned, then callback failed.
        """
        ret = self._run_cmd_impl(command, timeout)
        if not ret:
            return None

        if "command" not in ret or \
            "timeout" not in ret or \
            "returncode" not in ret or \
                "stdout" not in ret:
            raise BackendError(
                "_run_single_test needs to be implemented properly. "
                "Returned dictionary should contain correct data. "
                "Please check documentation")

        return ret
