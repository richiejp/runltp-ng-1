"""
Unittest for serial backend.
"""
import subprocess
import unittest.mock
import pytest
from ltp.runner import SerialRunner
from ltp.runner.base import RunnerError


def test_init():
    """
    Test class initialization.
    """
    with pytest.raises(ValueError):
        SerialRunner("")


def test_name(tmpdir):
    """
    Test name property.
    """
    target = tmpdir / "target"
    target.write("")

    assert SerialRunner(target).name == "serial"


def test_command(tmpdir):
    """
    Test start() method.
    """
    target = tmpdir / "target"
    target.write("")

    data = None

    def _emulate_shell(cmd):
        """
        Simple mock that gets command, execute it and write into target file.
        This function overrides TextIOWrapper::write method.
        """
        if not cmd:
            raise ValueError("command is empty")

        with open(target, 'a+') as ftarget:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True)

            stdout = proc.communicate()[0]
            ftarget.write(stdout.decode("utf-8"))

    runner = SerialRunner(target)
    runner.start()

    runner._file.write = unittest.mock.MagicMock()
    runner._file.write.side_effect = _emulate_shell

    data = runner.run_cmd("echo 'this-is-not-a-test'", 1)
    runner.stop()

    assert data["command"] == "echo 'this-is-not-a-test'"
    assert data["timeout"] == 1
    assert data["returncode"] == 0
    assert data["stdout"] == "this-is-not-a-test\n"


def test_command_timeout(tmpdir):
    """
    Test start() method when goes in timeout.
    """
    target = tmpdir / "target"
    target.write("")

    runner = SerialRunner(target)
    runner.start()

    # we are not handling the command, so we will run out of time anyway
    with pytest.raises(RunnerError):
        runner.run_cmd("echo 'this-is-not-a-test'", 0.01)
