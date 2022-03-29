"""
Unittest for shell module.
"""
import time
import signal
import threading
from ltp.runner import ShellRunner


def test_name():
    """
    Test name property.
    """
    assert ShellRunner().name == "shell"


def test_start():
    """
    Test start method.
    """
    ShellRunner().start()


def test_run_cmd():
    """
    Test run_cmd method.
    """
    ret = ShellRunner().run_cmd("test", 1)
    assert ret["command"] == "test"
    assert ret["returncode"] == 1
    assert ret["stdout"] == ""
    assert ret["timeout"] == 1


def test_run_cmd_timeout():
    """
    Test run_cmd method.
    """
    ret = ShellRunner().run_cmd("sleep 10", 0.1)
    assert ret["command"] == "sleep 10"
    assert ret["returncode"] == -signal.SIGKILL
    assert ret["stdout"] == ""
    assert ret["timeout"] == 0.1


def test_run_cmd_cwd(tmpdir):
    """
    Test run_cmd method using cwd initialization.
    """
    tmpfile = tmpdir / "myfile"
    tmpfile.write("")

    ret = ShellRunner(cwd=str(tmpdir)).run_cmd("ls", 10)
    assert ret["command"] == "ls"
    assert ret["returncode"] == 0
    assert ret["stdout"] == "myfile\n"
    assert ret["timeout"] == 10


def test_run_cmd_env():
    """
    Test run_cmd method using environment variables.
    """
    ret = ShellRunner(env=dict(HELLO="world")).run_cmd("echo -n $HELLO", 10)
    assert ret["command"] == "echo -n $HELLO"
    assert ret["returncode"] == 0
    assert ret["stdout"] == "world"
    assert ret["timeout"] == 10


def test_stop():
    """
    Test stop method.
    """
    shell = ShellRunner()

    class MyThread(threading.Thread):
        def __init__(self):
            super(MyThread, self).__init__()
            self.result = None
            self.daemon = True

        def run(self):
            self.result = shell.run_cmd("sleep 10", 20)

    thread = MyThread()
    thread.start()

    time.sleep(0.5)
    shell.stop()

    thread.join()
    ret = thread.result

    assert ret["command"] == "sleep 10"
    assert ret["returncode"] == -signal.SIGTERM
    assert ret["stdout"] == ""
    assert ret["timeout"] == 20


def test_force_stop():
    """
    Test force_stop method.
    """
    shell = ShellRunner()

    class MyThread(threading.Thread):
        def __init__(self):
            super(MyThread, self).__init__()
            self.result = None
            self.daemon = True

        def run(self):
            self.result = shell.run_cmd("sleep 10", 20)

    thread = MyThread()
    thread.start()

    time.sleep(0.5)
    shell.force_stop()

    thread.join()
    ret = thread.result

    assert ret["command"] == "sleep 10"
    assert ret["returncode"] == -signal.SIGKILL
    assert ret["stdout"] == ""
    assert ret["timeout"] == 20
