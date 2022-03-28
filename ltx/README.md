# Linux Test (Project) Executor

The `ltx` program runs on the system under test (SUT). It's primary
purpose is to run test executables in parallel and serialise the
results. It is a dumb program that executes simple commands sent to it
by a test scheduler (runltp-ng). The commands are encoded as
[MessagePack](https://github.com/msgpack/msgpack/blob/master/spec.md)
arrays as are the results.

The first element of the array is the message type, represented as an
integer. The rest of the array contents (if any) depend on the message
type.

In classic UNIX fashion, stdin and stdout are used to receive and send
commands. This makes LTX transport agnostic, a program such as
`socat`, `ssh` or just `sh` can be used to redirect the standard I/O
of LTX.

## Dependencies

LTX itself just needs Clang or GCC. The tests require Python 3.x with
pytest, msgpack and pexpect. Plus both Clang and GCC with support for
the address and undefined behavior sanitizers.

## Running

To run the tests use `pytest test.py`

## Messages

LTX is not intended to have a generic MessagePack parser. There are
several ways in which a message can be encoded. However you can assume
LTX only accepts the shortest possible encoding.

### Ping

Sent either to LTX or host. Pong is expected in return.

ID: 0
E.g: [0]

### Pong

Response to Ping.

ID: 1
E.g: [1]
