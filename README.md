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

Options parameters
==================

Each option has parameters which can be used to customize running behaviour.
Their syntax is `--option=param0:key1=param1:key2=param2`.

Install option
--------------

The `--install` option has branch name as the first parameter and then it
uses the following parameters to customize installation:
- **commit**: commit hash
- **repo**: repository location
- **m32**: uses 32bit dependences. It can be 0 or 1
- **install_dir**: LTP install directory

For example, `--install=master:commit=0f67c9851a9043d0ad68cef4648d103ba7908480`.

SUT option
----------

The `--sut` option has different parameters according with the first parameter
that is used. That's the name of the SUT we are going to use. Currently,
**host**, **qemu** and **ssh** are supported and they have the following
parameters:

**qemu** parameters:
- **image**: qcow2 image location
- **image_overlay**: copy image location
- **password**: root password (default: root)
- **system**: system architecture (default: x86_64)
- **ram**: RAM of the VM with qemu syntax (default: 2G)
- **smp**: number of CPUs (default: 2)
- **serial**: type of serial communication: isa or virtio (default: isa)
- **virtfs**: directory to mount inside VM
- **ro_image**: path to an image which will be exposed as read only

For example, `--sut=qemu:image=image.qcow2:smp=12:ram=10G:serial=virtio`.

**ssh** parameters:
- **host**: IP address or hostname of the SUT (default: localhost)
- **port**: TCP port of the service (default: 22)
- **user**: name of the user (default: root)
- **password**: user's password
- **timeout**: connection timeout is seconds (default: 10)
- **key_file**: private key location

For example, `--sut=ssh:host=10.0.10.1:port=2222:user=gigi:password=1234`.

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
