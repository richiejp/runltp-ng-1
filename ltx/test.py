import time
import pytest
import sys
import os
import subprocess as sp

from msgpack import packb, unpackb

proc = None
buf = b''

def read():
    return os.read(proc.stdout.fileno(), 8196)

def expect_exact(bs):
    global buf

    l = len(bs)

    while len(buf) < l:
        buf += read()

    for i in range(l):
        if buf[i] == bs[i]:
            continue

        raise ValueError(
            f"Expected {hex(bs[i])}, but got {hex(buf[i])} at {i} in '{buf.hex(' ')}'"
        )

    buf = buf[l:]


def expect_n_bytes(n):
    global buf

    while len(buf) < n:
        buf += read()

    buf = buf[n:]
    
def send(bs):
    assert proc.stdin.write(bs) == len(bs)
    # echo
    expect_exact(bs)

def reopen():
    global proc
    global buf

    if (proc != None):
        proc.kill()
        buf = b''

    proc = sp.Popen(
        ["./ltx"],
        bufsize=0,
        stdin=sp.PIPE,
        stdout=sp.PIPE,
        stderr=sp.PIPE
    )

def run(args):
    sp.run(args.split(' '),
           stdout=sp.PIPE, stderr=sp.STDOUT,
           check=True)
    
CFLAGS = '-Wall -Wextra -Werror -fno-omit-frame-pointer -fsanitize=address,undefined'
CFILES = 'ltx.c -o ltx'

def spawn():
    return LtxSpawn()

class TestLtx:
    def test_compile_gcc(self):
        run(f"gcc {CFLAGS} {CFILES}")

    def test_compile_clang(self):
        run(f"clang {CFLAGS} {CFILES}")

    def test_version_nolib(self):
        reopen()
        expect_exact(b'\x93\x04\xc0\xd9/[ltx.c:main:300] Linux Test Executor 0.0.1-dev\n')

    def test_version(self):
        reopen()
        expect_exact(packb([4, None, "[ltx.c:main:300] Linux Test Executor 0.0.1-dev\n"]))

    def test_ping_nolib(self):
        # Ping: [0]
        send(b'\x91\x00')
        # Pong: [1, time]
        expect_exact(b'\x92\x01\xcf')
        expect_n_bytes(8)

    def test_ping(self):
        # Ping
        send(packb([0]))
        # Pong
        expect_exact(packb([1, time.monotonic_ns()])[:-8])
        expect_n_bytes(8)




