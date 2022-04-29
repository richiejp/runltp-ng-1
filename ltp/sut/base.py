"""
.. module:: base
    :platform: Linux
    :synopsis: module containing SUT definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ltp import LTPException
from ltp.runner import Runner
from ltp.downloader import Downloader


class SUTError(LTPException):
    """
    Raised when an error occurs into SUT.
    """


class SUT:
    """
    A SUT is the target where tests are executed. It could be a remote
    host, a local host, a virtual machine instance, etc.
    """

    @property
    def name(self) -> str:
        """
        Name of the SUT.
        """
        raise NotImplementedError()

    @property
    def runner(self) -> Runner:
        """
        Object used to execute commands on target. It's None if communicate()
        has not been called yet.
        """
        raise NotImplementedError()

    @property
    def downloader(self) -> Downloader:
        """
        Object used to download files from target. It's None if communicate()
        has not been called yet.
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

    def stop(self) -> None:
        """
        Stop the current SUT session.
        """
        raise NotImplementedError()

    def force_stop(self) -> None:
        """
        Force stopping the current SUT session.
        """
        raise NotImplementedError()


class SUTFactory:
    """
    Create Factory implementations instances.
    """

    def create(self) -> SUT:
        """
        Create a new SUT object.
        """
        raise NotImplementedError()
