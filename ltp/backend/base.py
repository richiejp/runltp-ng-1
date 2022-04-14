"""
.. module:: base
    :platform: Linux
    :synopsis: module containing Backend definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ltp import LTPException
from ltp.runner import Runner
from ltp.downloader import Downloader


class BackendError(LTPException):
    """
    Raised when an error occurs into Backend.
    """


class Backend:
    """
    A backend is the target where tests are executed. It could be a remote
    host, a local host, a virtual machine instance, etc.
    """

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

    def communicate(self) -> None:
        """
        Start communicating with the backend and it initialize internal
        communication objects such as runner and downloader.
        """
        raise NotImplementedError()

    def stop(self) -> None:
        """
        Stop the current backend session.
        """
        raise NotImplementedError()

    def force_stop(self) -> None:
        """
        Force stopping the current backend session.
        """
        raise NotImplementedError()


class BackendFactory:
    """
    Create Factory implementations instances.
    """

    def create(self) -> Backend:
        """
        Create a new Backend object.
        """
        raise NotImplementedError()
