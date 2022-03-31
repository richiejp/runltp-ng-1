"""
Unittests for Backend package.
"""
import pytest
from ltp.backend import LocalBackend
from ltp.metadata import RuntestMetadata


class TestLocalBackend:
    """
    Test LocalBackend implementation.
    """

    def test_constructor(self):
        """
        Test class constructor.
        """
        with pytest.raises(ValueError):
            LocalBackend(None)

        with pytest.raises(ValueError):
            LocalBackend("this_path_doesnt_exist")

    @pytest.mark.usefixtures("prepare_tmpdir")
    def test_communicate(self, tmpdir):
        """
        Test communicate method.
        """
        tmp = tmpdir / "tmp"
        tmp.mkdir()

        backend = LocalBackend(str(tmpdir), tmp_dir=str(tmp))
        downloader, runner = backend.communicate()

        assert downloader is not None
        assert runner is not None

        target_file = tmpdir / "runtest" / "dirsuite0"
        local_file = tmpdir / "tmp" / "dirsuite0"

        downloader.fetch_file(target_file, local_file)
        metadata = RuntestMetadata()
        suite = metadata.read_suite(local_file)

        for test in suite.tests:
            cmd = f"{test.command} {' '.join(test.arguments)}"
            result = runner.run_cmd(cmd, 10)

            assert result is not None
            assert result["returncode"] == 0
