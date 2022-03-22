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
    Generic class to handle information on tests and testing suites.
    """

    @property
    def available_suites(self):
        """
        Return a list of the available testing suites.
        :returns: list
        """
        raise NotImplementedError()

    @property
    def available_tests(self):
        """
        Return a list of the available tests.
        :returns: list
        """
        raise NotImplementedError()

    def _read_test_impl(self, name: str):
        """
        This method has to be inherited to implement `read` method.
        :param name: name of the test.
        :type name: str
        :returns: dict
        """
        raise NotImplementedError()

    def read_test(self, name: str):
        """
        Return a specific test definition.
        :param name: name of the test.
        :type name: str
        :returns: a dictionary defined as following

            {
                "name": "mytestname",
                "command": "mycommand",
                "arguments": ["-p", "10"],
            }

        """
        data = self._read_test_impl(name)

        assert "name" in data
        assert isinstance(data["name"], str)

        assert "command" in data
        assert isinstance(data["command"], str)

        assert "arguments" in data
        assert isinstance(data["arguments"], list)

        return data

    def _read_suite_impl(self, name: str):
        """
        This method has to be inherited to implement `read_test_suite` method.
        :param name: name of the testing suite.
        :type name: str
        :returns: dict
        """
        raise NotImplementedError()

    def read_suite(self, name: str):
        """
        Return a specific testing suite definition.
        :param name: name of the testing suite.
        :type name: str
        :returns: a dictionary defined as following

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
        data = self._read_suite_impl(name)

        assert "name" in data
        assert isinstance("name", str)

        assert "tests" in data
        assert isinstance(data["tests"], list)

        return data
