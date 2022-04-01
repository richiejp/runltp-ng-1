"""
.. module:: base
    :platform: Linux
    :synopsis: module containing Backend definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""


class BackendError(Exception):
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
        Start communicating with the backend and it returns a set of objects to
        communicate with it.
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
