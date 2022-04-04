"""
Unit tests for dispatcher implementations.
"""
import pytest
from ltp.dispatcher import DispatcherError
from ltp.dispatcher import SerialDispatcher
from ltp.backend import LocalBackendFactory


class TestSerialDispatcher:
    """
    Test SerialDispatcher class implementation.
    """

    def test_bad_constructor(self, tmpdir):
        """
        Test constructor with bad arguments.
        """
        factory = LocalBackendFactory(str(tmpdir), str(tmpdir))

        with pytest.raises(ValueError):
            SerialDispatcher(str(tmpdir), None, factory)

        with pytest.raises(ValueError):
            SerialDispatcher(str(tmpdir), "this_folder_doesnt_exist", factory)

        with pytest.raises(ValueError):
            SerialDispatcher(str(tmpdir), str(tmpdir), None)

    @pytest.mark.usefixtures("prepare_tmpdir")
    def test_exec_suites_bad_args(self, tmpdir):
        """
        Test exec_suites() method with bad arguments.
        """
        factory = LocalBackendFactory(str(tmpdir), str(tmpdir))
        dispatcher = SerialDispatcher(str(tmpdir), str(tmpdir), factory)

        with pytest.raises(ValueError):
            dispatcher.exec_suites(None)

        with pytest.raises(DispatcherError):
            dispatcher.exec_suites(["this_suite_doesnt_exist"])

    @pytest.mark.usefixtures("prepare_tmpdir")
    def test_exec_suites(self, tmpdir):
        """
        Test exec_suites() method.
        """
        factory = LocalBackendFactory(str(tmpdir), str(tmpdir))
        dispatcher = SerialDispatcher(str(tmpdir), str(tmpdir), factory)

        results = dispatcher.exec_suites(suites=["dirsuite0", "dirsuite2"])

        assert results[0].suite.name == "dirsuite0"
        assert results[0].tests_results[0].passed == 1
        assert results[0].tests_results[0].failed == 0
        assert results[0].tests_results[0].skipped == 0
        assert results[0].tests_results[0].warnings == 0
        assert results[0].tests_results[0].broken == 0
        assert results[0].tests_results[0].return_code == 0
        assert results[0].tests_results[0].exec_time > 0

        assert results[1].suite.name == "dirsuite2"
        assert results[1].tests_results[0].passed == 0
        assert results[1].tests_results[0].failed == 0
        assert results[1].tests_results[0].skipped == 1
        assert results[1].tests_results[0].warnings == 0
        assert results[1].tests_results[0].broken == 0
        assert results[1].tests_results[0].return_code == 0
        assert results[1].tests_results[0].exec_time > 0
