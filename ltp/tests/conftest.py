"""
Generic tests configuration
"""
import os
import time
import stat
import logging
import threading
import subprocess
import socket
import pytest


class OpenSSHServer:
    """
    Class helper used to initialize a OpenSSH server.
    """

    def __init__(self, tmpdir: str, port: int = 2222) -> None:
        """
        :param port: ssh server port
        :type port: int
        """
        self._logger = logging.getLogger("sshserver")

        self._dir_name = os.path.dirname(__file__)
        self._server_key = os.path.abspath(
            os.path.sep.join([self._dir_name, 'id_rsa']))
        self._sshd_config_tmpl = os.path.abspath(
            os.path.sep.join([self._dir_name, 'sshd_config.tmpl']))
        self._sshd_config = os.path.abspath(
            os.path.sep.join([tmpdir, 'sshd_config']))

        self._port = port
        self._proc = None
        self._thread = None
        self._stop_thread = False

        # setup permissions on server key
        os.chmod(self._server_key, 0o600)

        # create sshd configuration file
        self._create_sshd_config()

    def _wait_for_port(self) -> None:
        """
        Wait until server is up.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while sock.connect_ex(('127.0.0.1', self._port)) != 0:
            time.sleep(.1)
        del sock

    def _create_sshd_config(self) -> None:
        """
        Create SSHD configuration file from template config expanding
        authorized_keys.
        """
        self._logger.info("creating SSHD configuration")

        # read template sshd configuration file
        with open(self._sshd_config_tmpl, 'r') as fh:
            tmpl = fh.read()

        # replace parent directory with the current directory
        auth_file = os.path.join(os.path.abspath(
            self._dir_name), 'authorized_keys')
        tmpl = tmpl.replace('{{authorized_keys}}', auth_file)

        self._logger.info("SSHD configuration is: %s", tmpl)

        # write sshd configuration file
        with open(self._sshd_config, 'w') as fh:
            for line in tmpl:
                fh.write(line)
            fh.write(os.linesep)

        self._logger.info(
            "'%s' configuration file has been created", self._sshd_config)

    def start(self) -> None:
        """
        Start ssh server.
        """
        cmd = [
            '/usr/sbin/sshd',
            '-ddd',
            '-D',
            '-p', str(self._port),
            '-h', self._server_key,
            '-f', self._sshd_config,
        ]

        self._logger.info("starting SSHD with command: %s", cmd)

        def run_server():
            self._proc = subprocess.Popen(
                " ".join(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                universal_newlines=True,
            )

            while self._proc.poll() is None:
                if self._stop_thread:
                    break

                line = self._proc.stdout.readline()
                if not line:
                    break

                self._logger.info(line.rstrip())

        self._thread = threading.Thread(target=run_server)
        self._thread.start()

        time.sleep(2)

        self._logger.info("service is up to use")

    def stop(self) -> None:
        """
        Stop ssh server.
        """
        if not self._proc or not self._thread:
            return

        self._logger.info("stopping SSHD service")

        self._proc.terminate()
        self._stop_thread = True
        self._thread.join(timeout=10)

        self._logger.info("service stopped")


@pytest.fixture
def ssh_server(tmpdir):
    """
    Fixture to run tests using a sshd instance.
    """
    server = OpenSSHServer(str(tmpdir), port=2222)
    server.start()
    yield
    server.stop()


@pytest.fixture
def prepare_tmpdir(tmpdir):
    """
    Prepare the temporary directory with LTP folders and tests.
    """
    os.environ["LTPROOT"] = str(tmpdir)
    os.environ["TMPDIR"] = str(tmpdir)

    # create testcases folder
    testcases = tmpdir.mkdir("testcases").mkdir("bin")

    script_sh = testcases.join("script.sh")
    script_sh.write(
        '#!/bin/bash\n'
        'echo ""\n'
        'echo ""\n'
        'echo "Summary:"\n'
        'echo "passed   $1"\n'
        'echo "failed   $2"\n'
        'echo "broken   $3"\n'
        'echo "skipped  $4"\n'
        'echo "warnings $5"\n'
    )

    st = os.stat(str(script_sh))
    os.chmod(str(script_sh), st.st_mode | stat.S_IEXEC)

    # create runtest folder
    root = tmpdir.mkdir("runtest")

    suitefile = root.join("dirsuite0")
    suitefile.write("dir01 script.sh 1 0 0 0 0")

    suitefile = root.join("dirsuite1")
    suitefile.write("dir02 script.sh 0 1 0 0 0")

    suitefile = root.join("dirsuite2")
    suitefile.write("dir03 script.sh 0 0 0 1 0")

    suitefile = root.join("dirsuite3")
    suitefile.write("dir04 script.sh 0 0 1 0 0")

    suitefile = root.join("dirsuite4")
    suitefile.write("dir05 script.sh 0 0 0 0 1")

    # create scenario_groups folder
    scenario_dir = tmpdir.mkdir("scenario_groups")

    scenario_def = scenario_dir.join("default")
    scenario_def.write("dirsuite0\ndirsuite1")

    scenario_def = scenario_dir.join("network")
    scenario_def.write("dirsuite2\ndirsuite3\ndirsuite4\ndirsuite5")
