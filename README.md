Runltp-ng
=========

LTP Next-Gen runner is a new version of the `runltp` script used by the
[Linux Test Project](https://github.com/linux-test-project/ltp).

Quickstart
==========

You can get help with `./runltp-ng --help`.

Some basic commands are the following:

    # show testing suites on host
    ./runltp-ng host --list

    # run syscalls and dio testing suites on host
    ./runltp-ng host -s syscalls dio

    # show packages to build LTP on the current system
    ./runltp-ng show-deps --build

    # show testing suites on host using different LTP installation folder
    LTPROOT=/opt/alternative_ltp ./runltp-ng host --list

    # run syscalls and dio testing suites on qemu VM
    ./runltp-ng qemu -i folder/image.qcow2 -s syscalls dio

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

Running tests
-------------

LTP tests can be run using different subcommands.

- `host`: execute LTP tests in the current system
- `qemu`: execute LTP tests in a qemu VM

> **_NOTE:_**  In order to execute tests inside a qemu instance, be sure to
> have qemu with kvm support installed.

Install LTP
-----------

The LTP installation can be done using the `runltp-ng install` command.
The following Linux distro are supported:

- openSUSE
- RHEL
- Debian
- Ubuntu
- Fedora
- Alpine

Development
===========

The application is validated using `pytest` and `pylint`.

Unit testing
------------

To run unittests, `pytest` has to be installed:

    pip install pytest
    pytest ./ltp/tests

Linting
-------

To run linting checks, `pylint` has to be installed:

    pip install pylint
    pylint --rcfile=pylint.ini ./ltp
