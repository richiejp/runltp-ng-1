Runltp-ng
=========

LTP Next-Gen runner is a new version of the `runltp` script used by the
[Linux Test Project](https://github.com/linux-test-project/ltp).

Quickstart
==========

You can get help with `./runltp-ng --help`.
Be sure to have properly set LTPROOT variable before running the commmand if you
are not already in the LTP folder.

> **_NOTE:_**  All features are experimental and they are under development.

Commands
--------

Some basic commands are the following:

    # show testing suites
    ./runltp-ng list

    # run syscalls and dio testing suite
    ./runltp-ng run --suites syscalls dio

    # show packages to build LTP on the current system
    ./runltp-ng show-deps --build

Please use `--help` to check all available options for the commands above.

Running tests
-------------

LTP tests can be run using `./runltp-ng run` command.

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

Environment
-----------

The following environment variables are supported and they can be used to
customize the runner behavior:

- `LTPROOT`: root of LTP installation
- `TMPDIR`: temporary directory for the tests
- `LTP_COLORIZE_OUTPUT`: tells LTP to show colors

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
