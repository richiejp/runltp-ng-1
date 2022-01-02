"""
Tests for the session module.
"""
import logging
import pytest
from ltp.session import LTPTest, LTPSuite, LTPSession, LTPTestError


@pytest.mark.usefixtures("prepare_tmpdir")
class TestLTPTest:
    """
    Tests for LTPTest class.
    """

    def test_constructor_bad_args(self):
        """
        Test class constructor with bad args
        """
        with pytest.raises(ValueError):
            LTPTest(None)

        with pytest.raises(ValueError):
            LTPTest("bad_formatting")

    def test_constructor_no_test_args(self):
        """
        Test class constructor with no test arguments.
        """
        test = LTPTest("mytest01 test01")
        assert test.name == "mytest01"
        assert test.command == "test01"
        assert len(test.args) == 0
        assert test.passed == 0
        assert test.failed == 0
        assert test.skipped == 0
        assert test.warnings == 0
        assert test.broken == 0

    def test_constructor_with_test_args(self):
        """
        Test class constructor with test arguments.
        """
        test = LTPTest("mytest01 test -a -t1 -p0")
        assert test.name == "mytest01"
        assert test.command == "test"
        assert len(test.args) == 3
        assert test.args == ["-a", "-t1", "-p0"]

    def test_run(self, caplog):
        """
        Test run method.
        """
        caplog.set_level(logging.INFO)
        test = LTPTest("dir01 ls")
        test.run()

        assert test.completed

        msgs = [x.message for x in caplog.records]
        assert "testcases" in msgs

    def test_run_pass(self, caplog):
        """
        Test run method with TPASS.
        """
        caplog.set_level(logging.INFO)
        test = LTPTest("mytest01 script.sh 1 0 0 0 0")
        test.run()

        assert test.completed

        assert test.passed == 1
        assert test.failed == 0
        assert test.skipped == 0
        assert test.broken == 0
        assert test.warnings == 0

    def test_run_fail(self, caplog):
        """
        Test run method with TFAIL.
        """
        caplog.set_level(logging.INFO)
        test = LTPTest("mytest01 script.sh 0 1 0 0 0")
        test.run()

        assert test.completed

        assert test.passed == 0
        assert test.failed == 1
        assert test.skipped == 0
        assert test.broken == 0
        assert test.warnings == 0

    def test_run_skip(self, caplog):
        """
        Test run method with TSKIP.
        """
        caplog.set_level(logging.INFO)
        test = LTPTest("mytest01 script.sh 0 0 0 1 0")
        test.run()

        assert test.completed

        assert test.passed == 0
        assert test.failed == 0
        assert test.skipped == 1
        assert test.broken == 0
        assert test.warnings == 0

    def test_run_brok(self, caplog):
        """
        Test run method with TBROK.
        """
        caplog.set_level(logging.INFO)
        test = LTPTest("mytest01 script.sh 0 0 1 0 0")
        test.run()

        assert test.completed

        assert test.passed == 0
        assert test.failed == 0
        assert test.skipped == 0
        assert test.broken == 1
        assert test.warnings == 0

    def test_run_warn(self, caplog):
        """
        Test run method with TWARN.
        """
        caplog.set_level(logging.INFO)
        test = LTPTest("mytest01 script.sh 0 0 0 0 1")
        test.run()

        assert test.completed

        assert test.passed == 0
        assert test.failed == 0
        assert test.skipped == 0
        assert test.broken == 0
        assert test.warnings == 1

    def test_run_with_args(self, caplog):
        """
        Test run method using args in the test declaration.
        """
        caplog.set_level(logging.INFO)
        test = LTPTest("dir01 ls -a")
        test.run()

        assert test.completed

        msgs = [x.message for x in caplog.records]
        assert "." in msgs
        assert ".." in msgs
        assert "testcases" in msgs

    def test_run_ltproot(self, tmpdir, caplog):
        """
        Test run method using LTPROOT from env vars.
        """
        caplog.set_level(logging.INFO)
        test = LTPTest("root01 echo $LTPROOT")
        test.run()

        assert test.completed

        msgs = [x.message for x in caplog.records]
        assert str(tmpdir) in msgs

    def test_run_tmpdir(self, tmpdir, caplog):
        """
        Test run method using TMPDIR from env vars.
        """
        caplog.set_level(logging.INFO)
        test = LTPTest("root01 echo $TMPDIR")
        test.run()

        assert test.completed

        msgs = [x.message for x in caplog.records]
        assert str(tmpdir) in msgs

    def test_run_exception(self, caplog):
        """
        Test run method when raising LTPTestError.
        """
        caplog.set_level(logging.DEBUG)
        with pytest.raises(LTPTestError, match="return code: 100"):
            test = LTPTest("dir01 script.sh 1 0 0 0 0; exit 100")
            test.run()

            assert test.completed

    def test_run_oldtest_fail(self):
        """
        Test run method when old test is failing.
        """
        test = LTPTest("dir01 exit 100")
        test.run()

        assert test.completed

        assert test.passed == 0
        assert test.failed == 1
        assert test.skipped == 0
        assert test.broken == 0
        assert test.warnings == 0

    def test_run_oldtest_pass(self):
        """
        Test run method when old test is passing.
        """
        test = LTPTest("dir01 exit 0")
        test.run()

        assert test.completed

        assert test.passed == 1
        assert test.failed == 0
        assert test.skipped == 0
        assert test.broken == 0
        assert test.warnings == 0


@pytest.mark.usefixtures("prepare_tmpdir")
class TestLTPSuite:
    """
    Test the LTPSuite class
    """

    def test_constructor_bad_args(self):
        """
        Test constructor with bad arguments.
        """
        with pytest.raises(ValueError):
            LTPSuite(None)

        with pytest.raises(ValueError):
            LTPSuite("this_path_doesnt_exist")

    def test_constructor(self, tmpdir):
        """
        Test constructor.
        """
        suitefile = tmpdir.join("dirsuite")
        suitefile.write("dir01 ls -l\n\ndir02 ls -a")
        suite = LTPSuite(suitefile)

        assert suite.name == "dirsuite"
        assert suite.tests[0].name == "dir01"
        assert suite.tests[0].command == "ls"
        assert suite.tests[0].args == ["-l"]
        assert suite.tests[1].name == "dir02"
        assert suite.tests[1].command == "ls"
        assert suite.tests[1].args == ["-a"]

    def test_run(self, tmpdir):
        """
        Test run method.
        """
        suitefile = tmpdir.join("dirsuite")
        suitefile.write("dir01 ls -l\n\ndir02 ls -a")
        suite = LTPSuite(suitefile)
        suite.run()

        assert suite.completed
        assert suite.passed == 2
        assert suite.failed == 0
        assert suite.skipped == 0
        assert suite.broken == 0
        assert suite.warnings == 0

        for test in suite.tests:
            assert test.completed


@pytest.mark.usefixtures("prepare_tmpdir")
class TestLTPSession:
    """
    Test the LTPSession class
    """

    def test_constructor(self):
        """
        Test constructor.
        """
        session = LTPSession()
        assert len(session.suites) == 5
        session.suites[0].name == "dirsuite0"
        session.suites[1].name == "dirsuite1"
        session.suites[2].name == "dirsuite2"
        session.suites[3].name == "dirsuite3"
        session.suites[4].name == "dirsuite4"

    def test_run_all(self, caplog):
        """
        Test run method with empty scenario.
        """
        caplog.set_level(logging.DEBUG)

        session = LTPSession()
        session.run()

        assert session.completed
        assert session.passed == 1
        assert session.failed == 1
        assert session.skipped == 1
        assert session.broken == 1
        assert session.warnings == 1

        for i in range(0, 5):
            assert session.suites[i].completed
            for test in session.suites[i].tests:
                assert test.completed

    def test_run_scenario_bad_args(self):
        """
        Test run_scenario method with bad arguments.
        """
        with pytest.raises(ValueError):
            session = LTPSession()
            session.run_scenario("this_scenario_doesnt_exist")
            assert not session.completed

    def test_run_scenario_default(self):
        """
        Test run_scenario method with default scenario.
        """
        session = LTPSession()
        session.run_scenario("default")

        assert session.completed
        assert session.passed == 1
        assert session.failed == 1
        assert session.skipped == 0
        assert session.broken == 0
        assert session.warnings == 0

        assert len(session.suites) == 5

        for suite in session.suites:
            if suite.name in ["dirsuite0", "dirsuite1"]:
                assert suite.completed
                for test in suite.tests:
                    assert test.completed
            else:
                assert not suite.completed
                for test in suite.tests:
                    assert not test.completed

    def test_run_scenario_network(self):
        """
        Test run_scenario method with network scenario.
        """
        session = LTPSession()
        session.run_scenario("network")

        assert session.completed
        assert session.passed == 0
        assert session.failed == 0
        assert session.skipped == 1
        assert session.broken == 1
        assert session.warnings == 1

        for suite in session.suites:
            if suite.name in ["dirsuite2", "dirsuite3", "dirsuite4"]:
                assert suite.completed
                for test in suite.tests:
                    assert test.completed
            else:
                assert not suite.completed
                for test in suite.tests:
                    assert not test.completed

    def test_run_single(self):
        """
        Test run method with network scenario.
        """
        session = LTPSession()
        session.run(suites=["dirsuite3"])

        assert session.completed
        assert session.passed == 0
        assert session.failed == 0
        assert session.skipped == 0
        assert session.broken == 1
        assert session.warnings == 0

        for suite in session.suites:
            if suite.name == "dirsuite3":
                assert suite.completed
                for test in suite.tests:
                    assert test.completed
            else:
                assert not suite.completed
                for test in suite.tests:
                    assert not test.completed
