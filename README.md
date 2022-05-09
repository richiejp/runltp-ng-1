Runltp-ng
=========

LTP Next-Gen runner is a new version of the `runltp` script used by the
[Linux Test Project](https://github.com/linux-test-project/ltp).

Quickstart
==========

Some basic commands are the following:

    # run syscalls and dio testing suites on host
    runltp-ng --run-suite syscalls dio

    # run syscalls and dio testing suites in qemu VM
    runltp-ng --sut=qemu:image=folder/image.qcow2 \
        --run-suite syscalls dio

    # run syscalls and dio testing suites via SSH
    runltp-ng --sut=ssh:host=10.0.10.1:key_file=folder/privkey_rsa \
        --run-suite syscalls dio

LTP can be installed using `--install` option as following:

    runltp-ng --install=master:commit=0f67c9851a9043d0ad68cef4648d103ba7908480

And it can be mixed up with `--sut` or `--run-suite` to install LTP
before testing:

    runltp-ng --install=master --sut=qemu:image=folder/image.qcow2 \
        --run-suite syscalls dio

It's possible to run a single command before running testing suites using
`--run-cmd` option as following:

    runltp-ng --run-cmd=/mnt/testcases/kernel/systemcalls/bpf/bpf_prog02 \
        --sut=qemu:image=folder/image.qcow2 \
        --run-suite syscalls dio

It can be used also to run a single command without running testing suites:

    runltp-ng --run-cmd=/mnt/testcases/kernel/systemcalls/bpf/bpf_prog02 \
        --sut=qemu:image=folder/image.qcow2

The following environment variables are supported and they can be used to
customize the runner behavior:

- `LTPROOT`: root of LTP installation
- `TMPDIR`: temporary directory of the application. By default it's `/tmp`
- `LTP_COLORIZE_OUTPUT`: tells LTP to show colors

Every session has a temporary directory which can be found in
`/<TMPDIR>/runltp-of<username>`. Inside this folder there's a symlink
called `latest`, pointing to the latest session's temporary directory, and the
application will rotate over 5 sessions.

Please use `--install help` and `--sut help` to see how to configure SUT and
install parameters.

Installation
============

Installation via setuptools
---------------------------

To install `runltp-ng` please use `pip` as following:

    pip install --prefix=<install directory> .

Be sure to initialize `PATH` and `PYTHONPATH` if no virtualenv is used.
When using virtualenv, just run:

    pip install .

Installation via distro packages
--------------------------------

Install `paramiko` and `scp` packages in your distribution, then run:

    ./runltp-ng

Development
===========

The application is validated using `pytest` and `pylint`.

Unit testing
------------

To run unittests, `pytest` has to be installed:

    pip install -e .
    pip install pytest
    pytest ./ltp/tests

Linting
-------

To run linting checks, `pylint` has to be installed:

    pip install pylint
    pylint --rcfile=pylint.ini ./ltp
