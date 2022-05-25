#!/usr/bin/ipython-3.9 -i

import os
import subprocess as sp
from msgpack import packb, unpackb

def read():
    return os.read(proc.stdout.fileno(), 1 << 21)

def write(bs):
    return proc.stdin.write(bs)

def reopen():
    global proc

    proc.kill()
    proc = sp.Popen(
        ["./ltx"],
        bufsize=0,
        stdin=sp.PIPE,
        stdout=sp.PIPE,
    )
    return read()

proc = sp.Popen(
    ["./ltx"],
    bufsize=0,
    stdin=sp.PIPE,
    stdout=sp.PIPE,
)
read()
