"""
Unittests for Backend package.
"""
import pytest
from ltp.backend import Backend
from ltp.backend import LocalBackend
from ltp.backend import LocalBackendFactory
from ltp.metadata import RuntestMetadata


class TestLocalBackend:
    """
    Test LocalBackend implementation.
    """

    def test_constructor(self, tmpdir):
        """
        Test class constructor.
        """
        with pytest.raises(ValueError):
            LocalBackend(None, str(tmpdir))

        with pytest.raises(ValueError):
            LocalBackend("this_path_doesnt_exist", str(tmpdir))

        with pytest.raises(ValueError):
            LocalBackend(str(tmpdir), None)

        with pytest.raises(ValueError):
            LocalBackend(str(tmpdir), "this_path_doesnt_exist")

    @pytest.mark.usefixtures("prepare_tmpdir")
    def test_communicate(self, tmpdir):
        """
        Test communicate method.
        """
        tmp = tmpdir / "tmp"
        tmp.mkdir()

        backend = LocalBackend(str(tmpdir), str(tmp))
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

    def test_factory_bad_args(self, tmpdir):
        """
        Test LocalBackendFactory create() method with bad arguments.
        """
        with pytest.raises(ValueError):
            LocalBackendFactory(None, str(tmpdir))

        with pytest.raises(ValueError):
            LocalBackendFactory("this_folder_doesnt_exist", str(tmpdir))

        with pytest.raises(ValueError):
            LocalBackendFactory(str(tmpdir), None)

        with pytest.raises(ValueError):
            LocalBackendFactory(str(tmpdir), "this_folder_doesnt_exist")

    def test_factory(self, tmpdir):
        """
        Test LocalBackendFactory create() method with good arguments..
        """
        factory = LocalBackendFactory(str(tmpdir), str(tmpdir))
        backend = factory.create()

        assert isinstance(backend, Backend)
