Runltp-ng
=========

LTP Next-Gen runner is a new version of the `runltp` script used by the
[Linux Test Project](https://github.com/linux-test-project/ltp).

Quickstart
==========

You can get help with `runltp-ng --help`. To install the application:

    virtualenv venv
    source venv/bin/activate

    python setup.py install

> **_NOTE:_**  All features are experimental and they are under development.

Showing tests
-------------

LTP tests can be shown using `runltp-ng list` command.

Running tests
-------------

LTP tests can be run using `runltp-ng run` command.

Install LTP
-----------

The LTP installation can be done using the `runltp-ng install` command.
The following Linux distro are supported:

- openSUSE
- Debian
- Ubuntu
- Fedora
- CentOS
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

    pip install pytest coverage
    pip install -e . # devel package install

    coverage run -m pytest
    coverage html

Linting
-------

To run linting checks, `pylint` has to be installed:

    pip install pylint
    pylint --rcfile=pylint.ini ./ltp
