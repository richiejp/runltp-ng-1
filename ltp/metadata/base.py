"""
.. module:: metadata
    :platform: Linux
    :synopsis: module for Metadata definition

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""


class MetadataError(Exception):
    """
    Raised when a error occurs during metadata operations.
    """


class Metadata:
    """
    This is an implementation used to load testing suite metadata
    rapresentation. Testing suites are usually defined inside a file that
    contains all tests information.
    """

    def _read_suite_impl(self, name: str):
        """
        This method has to be inherited to implement `read_test_suite` method.
        :param name: name of the testing suite.
        :type name: str
        :returns: dict
        """
        raise NotImplementedError()

    @staticmethod
    def _validate(data: dict) -> None:
        """
        Validate testing suite data rapresentation.
        :param data: testing suite data rapresentation
        :type data: a dictionary defined as following

            {
                "name": "mysuite",
                "tests": [
                    {
                        "name": "mytestname",
                        "command": "mycommand",
                        "arguments": ["-p", "10"],
                    }
                ]
            }

        """
        if "name" not in data:
            raise MetadataError("Testing suite name is missing")

        if "tests" not in data:
            raise MetadataError("Tests list is missing")

        for test in data["tests"]:
            if "name" not in test:
                raise MetadataError("Test name is missing")

            if "command" not in test:
                raise MetadataError("Test command is missing")

            if "arguments" not in test:
                raise MetadataError("Test arguments are missing")

    def read_suite(self, name: str):
        """
        Return a specific testing suite definition.
        :param name: name of the testing suite.
        :type name: str
        :returns: dict
        """
        data = self._read_suite_impl(name)
        self._validate(data)

        return data
