#!/usr/bin/pytest-3.9 --timeout=5

import time
import pytest
import sys
import os
import re
import subprocess as sp

from msgpack import packb, unpackb, Unpacker, OutOfData

start_time = None
proc = None
buf = b''

def read():
    return os.read(proc.stdout.fileno(), 1 << 21)

def expect_exact(bs):
    global buf

    l = len(bs)

    while len(buf) < l:
        buf += read()

    for i in range(l):
        if buf[i] == bs[i]:
            continue

        raise ValueError(
            f"Expected {hex(bs[i])}, but got {hex(buf[i])} at {i} in '{buf.hex(' ')}' / {buf}"
        )

    buf = buf[l:]


def expect_n_bytes(n):
    global buf

    while len(buf) < n:
        buf += read()

    buf = buf[n:]

def unpack_next():
    global buf
    u = Unpacker()
    o = None

    u.feed(buf)

    while o == None:
        try:
            o = u.unpack()
        except OutOfData:
            d = read()
            buf += d
            u.feed(d)

    buf = buf[u.tell():]

    return o

def check_time(t):
    assert(start_time < t)
    assert(t < time.monotonic_ns())
    
def send(bs):
    assert os.write(proc.stdin.fileno(), bs) == len(bs)
    # echo
    expect_exact(bs)

def reopen():
    global proc
    global buf

    if (proc != None):
        proc.kill()
        buf = b''

    proc = sp.Popen(
        ["strace", "-e", "read,write", "-x", "./ltx"],
        bufsize=0,
        stdin=sp.PIPE,
        stdout=sp.PIPE,
    )

def run(args):
    sp.run(args.split(' '),
           stdout=sp.PIPE, stderr=sp.STDOUT,
           check=True)
    
CFLAGS = '-Wall -Wextra -Werror -g -fno-omit-frame-pointer -fsanitize=address,undefined'
CFILES = 'ltx.c -o ltx'

def spawn():
    return LtxSpawn()

class TestLtx:
    def test_compile_gcc(self):
        run(f"gcc {CFLAGS} {CFILES}")

    def test_compile_clang(self):
        run(f"clang {CFLAGS} {CFILES}")

    def test_version(self):
        global start_time
        reopen()
        send(packb([10]))
        ver_msg = unpack_next()
        
        assert(len(ver_msg) == 4)
        assert(ver_msg[0] == 4)
        assert(ver_msg[1] == None)
        start_time = ver_msg[2]
        assert(re.match(r'LTX Version=0.0.1-dev', ver_msg[3]) != None)

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
        pong = unpack_next()
        assert(len(pong) == 2)
        assert(pong[0] == 1)
        check_time(pong[1])

    def test_ping_flood(self):
        pings = packb([[0] for _ in range(2048)])[3:]
        assert proc.stdin.write(pings) == len(pings)

        ping_eg = packb([0])
        pong_eg = packb([1, time.monotonic_ns()])
        for _ in range(2048):
            expect_exact(ping_eg)
            expect_exact(pong_eg[:-8])
            expect_n_bytes(8)

    def test_exec(self):
        send(packb([3, 0, "/usr/bin/uname"]))
        log = unpack_next()
        assert(log[0] == 4)
        assert(log[1] == 0)
        check_time(log[2])
        assert(log[3] == "Linux\n")

        res = unpack_next()
        assert(len(res) == 5)
        assert(res[0] == 5)
        assert(res[1] == 0)
        check_time(res[2])
        assert(res[3] == 1)
        assert(res[4] == 0)

    def test_set_file(self, tmp_path):
        pattern = b'AaXa\x00\x01\x02Zz' * 2048
        d = tmp_path / 'get_file'
        d.mkdir()
        p = d / 'pattern'

        send(packb([7, p.as_posix(), pattern]))

        content = p.read_bytes()
        assert(content == pattern)

        send(packb([0]))
        assert(unpack_next()[0] == 1)
        
    def test_get_file(self, tmp_path):
        pattern = b'AaXa\x00\x01\x02Zz' * 2048
        d = tmp_path / 'get_file'
        d.mkdir()
        p = d / 'pattern'

        p.write_bytes(pattern)
        send(packb([6, p.as_posix()]))

        data = unpack_next()
        assert(data[0] == 8)
        assert(data[1] == pattern)

    def test_kill(self):
        send(packb([3, 1, "/usr/bin/sleep", "10"]))
        time.sleep(0.1)
        send(packb([9, 1]))

        res = unpack_next()
        assert(res[0] == 5)
        assert(res[1] == 1)
        check_time(res[2])
        assert(res[3] == 2)
        assert(res[4] == 9)
