"""
Unit tests for metadata implementations.
"""
import pytest
from ltp.metadata import RuntestMetadata


@pytest.mark.usefixtures("prepare_tmpdir")
class TestRuntestMetadata:
    """
    Test the RuntestMetadata implementation.
    """

    def test_available_suites(self, tmpdir):
        """
        Test available_suites property.
        """
        meta = RuntestMetadata(str(tmpdir) + "/runtest")
        suites = meta.available_suites

        assert len(suites) == 5
        for i in range(0, 5):
            assert "dirsuite%d" % i in suites

    def test_available_tests(self, tmpdir):
        """
        Test available_tests property.
        """
        meta = RuntestMetadata(str(tmpdir) + "/runtest")
        tests = meta.available_tests

        assert len(tests) == 5
        for i in range(1, 6):
            assert "dir0%d" % i in tests

    def test_read_test(self, tmpdir):
        """
        Test read_test method.
        """
        meta = RuntestMetadata(str(tmpdir) + "/runtest")
        test = meta.read_test("dir01")

        assert test["name"] == "dir01"
        assert test["command"] == "script.sh"
        assert test["arguments"] == ['1', '0', '0', '0', '0']

    def test_read_suite(self, tmpdir):
        """
        Test read_suite method.
        """
        meta = RuntestMetadata(str(tmpdir) + "/runtest")
        test = meta.read_suite("dirsuite0")

        assert test["name"] == "dirsuite0"
        assert test["tests"] == [{
            "name": "dir01",
            "command": "script.sh",
            "arguments":  ['1', '0', '0', '0', '0']
        }]
