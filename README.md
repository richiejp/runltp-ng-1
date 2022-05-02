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
    runltp-ng --sut=qemu:image=folder/image.qcow2 --run-suite syscalls dio

    # run syscalls and dio testing suites via SSH
    runltp-ng --sut=ssh:host=10.0.10.1:key_file=privkey_rsa --run-suite syscalls dio

Please use `--help` to check all available options for the commands above.

The following environment variables are supported and they can be used to
customize the runner behavior:

- `LTPROOT`: root of LTP installation
- `TMPDIR`: temporary directory of the application. By default it's `/tmp`
- `LTP_COLORIZE_OUTPUT`: tells LTP to show colors

Every session has a temporary directory which can be found in
`/<TMPDIR>/runltp-of<username>`. Inside this folder there's a symlink
called `latest`, pointing to the latest session's temporary directory, and the
application will rotate over 5 sessions.

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
