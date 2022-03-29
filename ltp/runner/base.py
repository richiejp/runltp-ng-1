"""
.. module:: base
    :platform: Linux
    :synopsis: module containing Runner definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""


class RunnerError(Exception):
    """
    Raised when an error occurs inside Runner.
    """


class Runner:
    """
    Runner permits to execute commands on target using a specific protocol.
    """

    @property
    def name(self) -> str:
        """
        Name of the runner.
        :returns: str
        """
        raise NotImplementedError()

    def start(self) -> None:
        """
        Start runner.
        """
        raise NotImplementedError()

    def stop(self, timeout: int = 0) -> None:
        """
        Stop Runner.
        :param timeout: timeout before raising an exception. If 0, no timeout
            will be applied.
        :type timeout: int
        """
        raise NotImplementedError()

    def force_stop(self) -> None:
        """
        Forcly stop the Runner.
        """
        raise NotImplementedError()

    def _run_cmd_impl(self, command: str, timeout: int) -> dict:
        """
        Run a command on target. This has to be implemented by the class that
        is inheriting Runner class.
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
            raise RunnerError(
                "_run_single_test needs to be implemented properly. "
                "Returned dictionary should contain correct data. "
                "Please check documentation")

        return ret
