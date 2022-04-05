"""
.. module:: base
    :platform: Linux
    :synopsis: module containing Backend definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ltp import LTPException


class BackendError(LTPException):
    """
    Raised when an error occurs into Backend.
    """


class Backend:
    """
    A backend is the target where tests are executed. It could be a remote
    host, a local host, a virtual machine instance, etc.
    """

    def communicate(self) -> set:
        """
        Start communicating with the backend and it returns Downloader and
        Runner implementations to communicate. If backend is already running,
        the current Downloader and Runner implementations will be given.
        :returns: Downloader, Runner
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
