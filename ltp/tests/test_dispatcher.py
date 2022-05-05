"""
Unit tests for dispatcher implementations.
"""
import pytest
from ltp.channel.base import ChannelTimeoutError
from ltp.common.events import Events
from ltp.dispatcher import SerialDispatcher
from ltp.dispatcher import SuiteTimeoutError
from ltp.sut import LocalSUT


class DummyEvents(Events):
    """
    A dummy events class for dispatcher implementations.
    """


class TestSerialDispatcher:
    """
    Test SerialDispatcher class implementation.
    """

    def test_bad_constructor(self, tmpdir):
        """
        Test constructor with bad arguments.
        """
        sut = LocalSUT()

        with pytest.raises(ValueError):
            SerialDispatcher(
                tmpdir=str(tmpdir),
                ltpdir=None,
                sut=sut,
                events=DummyEvents())

        with pytest.raises(ValueError):
            SerialDispatcher(
                ltpdir=str(tmpdir),
                tmpdir="this_folder_doesnt_exist",
                sut=sut,
                events=DummyEvents())

        with pytest.raises(ValueError):
            SerialDispatcher(
                tmpdir=str(tmpdir),
                ltpdir=str(tmpdir),
                sut=None,
                events=DummyEvents())

        with pytest.raises(ValueError):
            SerialDispatcher(
                tmpdir=str(tmpdir),
                ltpdir=str(tmpdir),
                sut=sut,
                events=None)

    @pytest.mark.usefixtures("prepare_tmpdir")
    def test_exec_suites_bad_args(self, tmpdir):
        """
        Test exec_suites() method with bad arguments.
        """
        sut = LocalSUT()
        dispatcher = SerialDispatcher(
            tmpdir=str(tmpdir),
            ltpdir=str(tmpdir),
            sut=sut,
            events=DummyEvents())

        sut.communicate()

        try:
            with pytest.raises(ValueError):
                dispatcher.exec_suites(None)

            with pytest.raises(ValueError):
                dispatcher.exec_suites(["this_suite_doesnt_exist"])
        finally:
            sut.stop()

    @pytest.mark.usefixtures("prepare_tmpdir")
    def test_exec_suites(self, tmpdir):
        """
        Test exec_suites() method.
        """
        sut = LocalSUT()
        dispatcher = SerialDispatcher(
            tmpdir=str(tmpdir),
            ltpdir=str(tmpdir),
            sut=sut,
            events=DummyEvents())

        sut.communicate()

        try:
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
        finally:
            sut.stop()

    def test_exec_suites_suite_timeout(self, tmpdir):
        """
        Test exec_suites() method when suite timeout occurs.
        """
        # create testcases folder
        tmpdir.mkdir("testcases").mkdir("bin")

        # create runtest folder
        root = tmpdir.mkdir("runtest")

        suitefile = root.join("sleepsuite")
        suitefile.write("sleep sleep 2")

        sut = LocalSUT()
        dispatcher = SerialDispatcher(
            tmpdir=str(tmpdir),
            ltpdir=str(tmpdir),
            sut=sut,
            events=DummyEvents(),
            suite_timeout=1,
            test_timeout=10)

        sut.communicate()

        try:
            with pytest.raises(SuiteTimeoutError):
                dispatcher.exec_suites(suites=["sleepsuite"])
        finally:
            sut.stop()

    def test_exec_suites_test_timeout(self, tmpdir):
        """
        Test exec_suites() method when test timeout occurs.
        """
        # create testcases folder
        tmpdir.mkdir("testcases").mkdir("bin")

        # create runtest folder
        root = tmpdir.mkdir("runtest")

        suitefile = root.join("sleepsuite")
        suitefile.write("sleep sleep 2")

        sut = LocalSUT()
        dispatcher = SerialDispatcher(
            tmpdir=str(tmpdir),
            ltpdir=str(tmpdir),
            sut=sut,
            events=DummyEvents(),
            suite_timeout=10,
            test_timeout=1)

        sut.communicate()

        try:
            with pytest.raises(ChannelTimeoutError):
                dispatcher.exec_suites(suites=["sleepsuite"])
        finally:
            sut.stop()
