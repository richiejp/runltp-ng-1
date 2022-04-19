import os
import subprocess as sp
from msgpack import packb, unpackb

import IPython

proc = sp.Popen(
    ["./ltx"],
    bufsize=0,
    stdin=sp.PIPE,
    stdout=sp.PIPE,
)

def read():
    return os.read(proc.stdout.fileno(), 8196)

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

IPython.embed()
