import pytest
import signal
import sys
import subprocess as sp
import threading
from queue import Queue, Empty

from msgpack import packb, unpackb
from pexpect import run
from pexpect.popen_spawn import PopenSpawn
from pexpect.spawnbase import SpawnBase

class LtxSpawn(PopenSpawn):
    """Overrides PopenSpawns __init__ to seperate stderr from stdout

    Copy and pasted from popen_spawn.py
    """
    def __init__(self):
        super(PopenSpawn, self).__init__(timeout=1)

        self.proc = sp.Popen(
            ["./ltx"],
            bufsize=0,
            stdin=sp.PIPE,
            stderr=sp.PIPE,
            stdout=sp.PIPE,
        )
        self.pid = self.proc.pid
        self.closed = False
        self._buf = self.string_type()

        self._read_queue = Queue()
        self._read_thread = threading.Thread(target=self._read_incoming)
        self._read_thread.setDaemon(True)
        self._read_thread.start()

CFLAGS = '-Wall -Wextra -Werror -fno-omit-frame-pointer -fsanitize=address,undefined'
CFILES = 'ltx.c -o ltx'

def spawn():
    return LtxSpawn()

class TestLtx:
    def test_compile_gcc(self):
        log, status = run('gcc {} {}'.format(CFLAGS, CFILES), withexitstatus=1)
        print(log)
        assert status == 0

    def test_compile_clang(self):
        log, status = run('clang {} {}'.format(CFLAGS, CFILES), withexitstatus=1)
        print(log)
        assert status == 0

    def test_version_nolib(self):
        p = spawn()

        assert p.expect_exact(b'\x93\x02\xc0\xd9/[ltx.c:main:245] Linux Test Executor 0.0.1-dev\n') == 0

        p.kill(signal.SIGTERM)
        p.wait()

    def test_version(self):
        p = spawn()
        p.logfile = sys.stdout.buffer

        assert p.expect_exact(packb([2, None, "[ltx.c:main:245] Linux Test Executor 0.0.1-dev\n"])) == 0

        p.kill(signal.SIGTERM)
        p.wait()

    def test_ping_nolib(self):
        p = spawn()

        # Ping: [0]
        assert p.send(b'\x91\x00') == 2
        # Pong: [0]
        assert p.expect_exact(b'\x91\x00') == 0

        p.kill(signal.SIGTERM)
        p.wait()

    def test_ping(self):
        p = spawn()

        # Ping
        assert p.send(packb([0])) == 2
        # Pong
        assert p.expect_exact(packb([0])) == 0

        p.kill(signal.SIGTERM)
        p.wait()



