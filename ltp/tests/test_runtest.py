"""
Unit tests for metadata implementations.
"""
import pytest
from ltp.metadata import RuntestMetadata
from ltp.metadata import MetadataError


@pytest.fixture(autouse=True)
def create_suites(tmpdir):
    """
    Create testing suites.
    """
    root = tmpdir.mkdir("runtest")

    suitefile = root.join("suite01")
    suitefile.write("mytest01 mybin -a\n"
                    "mytest02 mybin -b\n"
                    "mytest03 mybin -c\n"
                    "mytest04 mybin -d\n")

    suitefile = root.join("suite02")
    suitefile.write("mytest05 mybin -a\n"
                    "mytest06 mybin -b\n"
                    "mytest07 mybin -c\n"
                    "mytest08 mybin -d\n")


class TestRuntestMetadata:
    """
    Test RuntestMetadata implementations.
    """

    def test_no_read_suite(self, tmpdir):
        """
        Test read_suite method.
        """
        meta = RuntestMetadata(str(tmpdir) + "/runtest")

        with pytest.raises(MetadataError):
            meta.read_suite("dirsuiteXYZ")

    def test_read_suite(self, tmpdir):
        """
        Test read_suite method.
        """
        meta = RuntestMetadata(str(tmpdir) + "/runtest")
        test = meta.read_suite("suite01")

        assert test["name"] == "suite01"
        assert {
            "name": "mytest01",
            "command": "mybin",
            "arguments":  ['-a'],
        } in test["tests"]

        assert {
            "name": "mytest01",
            "command": "mybin",
            "arguments":  ['-a'],
        } in test["tests"]
        assert {
            "name": "mytest02",
            "command": "mybin",
            "arguments":  ['-b'],
        } in test["tests"]
        assert {
            "name": "mytest03",
            "command": "mybin",
            "arguments":  ['-c'],
        } in test["tests"]
        assert {
            "name": "mytest04",
            "command": "mybin",
            "arguments":  ['-d'],
        } in test["tests"]

        test = meta.read_suite("suite02")
        assert {
            "name": "mytest05",
            "command": "mybin",
            "arguments":  ['-a'],
        } in test["tests"]

        assert {
            "name": "mytest06",
            "command": "mybin",
            "arguments":  ['-b'],
        } in test["tests"]
        assert {
            "name": "mytest07",
            "command": "mybin",
            "arguments":  ['-c'],
        } in test["tests"]
        assert {
            "name": "mytest08",
            "command": "mybin",
            "arguments":  ['-d'],
        } in test["tests"]
