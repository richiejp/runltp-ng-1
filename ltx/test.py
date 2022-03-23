import pytest
import signal
from msgpack import packb, unpackb
from pexpect import run
from pexpect.popen_spawn import PopenSpawn as spawn

CFLAGS = '-Wall -Wextra -Werror -fno-omit-frame-pointer -fsanitize=address,undefined'
CFILES = 'ltx.c -o ltx'

class TestLtx:
    def test_compile_gcc(self):
        log, status = run('gcc {} {}'.format(CFLAGS, CFILES), withexitstatus=1)
        print(log)
        assert status == 0

    def test_compile_clang(self):
        log, status = run('clang {} {}'.format(CFLAGS, CFILES), withexitstatus=1)
        print(log)
        assert status == 0

    def test_ping_nolib(self):
        p = spawn('./ltx', timeout=1)

        # Ping: [0]
        assert p.send(b'\x91\x00') == 2
        # Pong: [1]
        assert p.expect(b'\x91\x01') == 0

        p.kill(signal.SIGTERM)
        p.wait()

    def test_ping(self):
        p = spawn('./ltx', timeout=1)

        # Ping
        assert p.send(packb([0])) == 2
        # Pong
        assert p.expect(packb([1])) == 0

        p.kill(signal.SIGTERM)
        p.wait()



