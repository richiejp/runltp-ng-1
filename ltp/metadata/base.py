"""
.. module:: metadata
    :platform: Linux
    :synopsis: module for Metadata definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
from ltp import LTPException


class Suite:
    """
    Testing suite definition class.
    """

    def __init__(self, name: str, tests: list) -> None:
        """
        :param name: name of the testing suite
        :type name: str
        :param tests: tests of the suite
        :type tests: list
        """
        self._name = name
        self._tests = tests

    def __repr__(self) -> str:
        return \
            f"name: '{self._name}'," \
            f"tests: {self._tests}"

    @property
    def name(self):
        """
        Name of the testing suite.
        """
        return self._name

    @property
    def tests(self):
        """
        Tests definitions.
        """
        return self._tests


class Test:
    """
    Test definition class.
    """

    def __init__(self, name: str, cmd: str, args: list) -> None:
        """
        :param name: name of the test
        :type name: str
        :param cmd: command to execute
        :type cmd: str
        :param args: list of arguments
        :type args: list(str)
        """
        self._name = name
        self._cmd = cmd
        self._args = args

    def __repr__(self) -> str:
        return \
            f"name: '{self._name}'," \
            f"commmand: '{self._cmd}'," \
            f"arguments: {self._args}"

    @property
    def name(self):
        """
        Name of the test.
        """
        return self._name

    @property
    def command(self):
        """
        Command to execute test.
        """
        return self._cmd

    @property
    def arguments(self):
        """
        Arguments of the command.
        """
        return self._args


class MetadataError(LTPException):
    """
    Raised when a error occurs during metadata operations.
    """


class Metadata:
    """
    This is an implementation used to load testing suite metadata
    rapresentation. Testing suites are usually defined inside a file that
    contains all tests information.
    """

    def read_suite(self, suite_path: str) -> Suite:
        """
        Read a testing suite file and return a Suite object.
        :param suite_path: testing suite file path
        :type suite_path: str
        :returns: dict
        """
        raise NotImplementedError()
