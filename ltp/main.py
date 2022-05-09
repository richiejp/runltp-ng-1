"""
.. module:: main
    :platform: Linux
    :synopsis: main script

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import argparse
from argparse import ArgumentParser
from argparse import Namespace
from ltp.session import Session


def _from_params_to_config(params: list) -> dict:
    """
    Return a configuration as dictionary according with input parameters
    given to the commandline option.
    """
    config = {}
    for param in params:
        if '=' not in param:
            raise argparse.ArgumentTypeError(
                f"Missing '=' assignment in '{param}' parameter")

        data = param.split('=')
        key = data[0]
        value = data[1]

        if not key:
            raise argparse.ArgumentTypeError(
                f"Empty key for '{param}' parameter")

        if not key:
            raise argparse.ArgumentTypeError(
                f"Empty value for '{param}' parameter")

        config[key] = value

    return config


def _get_qemu_config(params: list) -> dict:
    """
    Return qemu configuration.
    """
    config = _from_params_to_config(params)

    if "image" not in config:
        raise argparse.ArgumentTypeError(
            "'image' parameter is required by qemu SUT")

    defaults = (
        'image',
        'image_overlay',
        'password',
        'system',
        'ram',
        'smp',
        'serial',
        'ro_image',
        'virtfs'
    )

    if not set(config).issubset(defaults):
        raise argparse.ArgumentTypeError(
            "Some parameters are not supported. "
            f"Please use the following: {', '.join(defaults)}")

    if "smp" in config:
        if not str.isdigit(config["smp"]):
            raise argparse.ArgumentTypeError("smp must be and integer")

    return config


def _get_ssh_config(params: list) -> dict:
    """
    Return the SSH SUT configuration.
    """
    config = _from_params_to_config(params)

    if 'host' not in config:
        raise argparse.ArgumentTypeError(
            "'host' parameter is required by qemu SUT")

    defaults = (
        'host',
        'port',
        'user',
        'password',
        'key_file',
        'timeout',
    )

    if not set(config).issubset(defaults):
        raise argparse.ArgumentTypeError(
            "Some parameters are not supported. "
            f"Please use the following: {', '.join(defaults)}")

    if "port" in config:
        port = config["port"]
        if not str.isdigit(port) and int(port) not in range(1, 65536):
            raise argparse.ArgumentTypeError(
                "port must be and integer inside [1-65535]")

    if "timeout" in config:
        if not str.isdigit(config["timeout"]):
            raise argparse.ArgumentTypeError("timeout must be and integer")

    return config


def _sut_config(value: str) -> dict:
    """
    Return a SUT configuration according with input string.
    Format for value is, for example:

        qemu:ram=4G:smp=4:image=/local/vm.qcow2:virtfs=/opt/ltp:password=123

    """
    if value == "help":
        msg = "--sut option supports the following syntax:\n"
        msg += "\n\t<SUT>:<param1>=<value1>:<param2>=<value2>:..\n\n"
        msg += "Supported SUT:\n"
        msg += "\thost: current machine (default)\n"
        msg += "\tqemu: Qemu virtual machine\n"
        msg += "\tssh: SSH server\n"
        msg += "\nqemu parameters:\n"
        msg += "\timage: qcow2 image location\n"
        msg += "\timage_overlay: image copy location\n"
        msg += "\tpassowrd: root password (default: root)\n"
        msg += "\tsystem: system architecture (default: x86_64\n"
        msg += "\tram: RAM of the VM (default: 2G)\n"
        msg += "\tsmp: number of CPUs (default: 2)\n"
        msg += "\tserial: type of serial protocol. isa|virtio (default: isa)\n"
        msg += "\tvirtfs: directory to mount inside VM\n"
        msg += "\tro_image: path of the image that will exposed as read only\n"
        msg += "\nssh parameters:\n"
        msg += "\thost: IP address of the SUT (default: localhost)\n"
        msg += "\tport: TCP port of the service (default: 22)\n"
        msg += "\tuser: name of the user (default: root)\n"
        msg += "\tpassword: user's password\n"
        msg += "\ttimeout: connection timeout in seconds (default: 10)\n"
        msg += "\tkey_file: private key location\n"
        msg += "\nhost parameters are not present.\n"

        return dict(help=msg)

    if not value:
        raise argparse.ArgumentTypeError("SUT parameters can't be empty")

    params = value.split(':')
    name = params[0]

    config = None
    if name == 'qemu':
        config = _get_qemu_config(params[1:])
    elif name == 'ssh':
        config = _get_ssh_config(params[1:])
    elif name == 'host':
        config = _from_params_to_config(params[1:])
    else:
        raise argparse.ArgumentTypeError(f"'{name}' SUT is not supported")

    config['name'] = name

    return config


def _install_config(value: str) -> dict:
    """
    Return an install configuration according with the input string.
    Format for value is, for example:

        master:commit=8f308953c60cdd25e372e8c58a3c963ab98be276

    """
    if value == "help":
        msg = "--install option supports the following syntax:\n"
        msg += "\n\t<branch>:<param1>=<value1>:<param2>=<value2>:..\n\n"
        msg += "Default branch is \"master\" and supported parameters are:\n"
        msg += "\tcommit: SHA commit\n"
        msg += "\trepo: repository location\n"
        msg += "\tm32: install 32bit packages. Can be 0 or 1 (optional)\n"
        msg += "\tinstall_dir: LTP install directory (default: /opt/ltp)\n"

        return dict(help=msg)

    if not value:
        raise argparse.ArgumentTypeError("Install parameters can't be empty")

    params = value.split(':')
    branch = params[0]
    if '=' in branch:
        raise argparse.ArgumentTypeError(
            "First --install element must be the git branch")

    config = _from_params_to_config(params[1:])

    defaults = (
        'commit',
        'repo',
        'm32',
        'install_dir',
    )

    if not set(config).issubset(defaults):
        raise argparse.ArgumentTypeError(
            "Some parameters are not supported. "
            f"Please use the following: {', '.join(defaults)}")

    if "m32" in config:
        m32 = config["m32"]
        if not str.isdigit(m32) and m32 not in ["0", "1"]:
            raise argparse.ArgumentTypeError("m32 must be 0 or 1")

    if 'repo' not in config:
        config['repo'] = 'http://github.com/linux-test-project/ltp.git'

    config['branch'] = branch

    return config


def _ltp_run(parser: ArgumentParser, args: Namespace) -> None:
    """
    Handle runltp-ng command options.
    """
    if args.sut and "help" in args.sut:
        print(args.sut["help"])
        return

    if args.install and "help" in args.install:
        print(args.install["help"])
        return

    if args.json_report and os.path.exists(args.json_report):
        parser.error(f"JSON report file already exists: {args.json_report}")

    if not args.run_suite and not args.run_cmd and not args.install:
        parser.error("--run-suite/--run-cmd or --install are required")

    try:
        session = Session(
            verbose=args.verbose,
            suite_timeout=args.suite_timeout,
            exec_timeout=args.exec_timeout)

        session.run_single(
            args.sut,
            args.install,
            args.json_report,
            args.run_suite,
            args.run_cmd)
    except ValueError as err:
        print(err)


def run() -> None:
    """
    Entry point of the application.
    """
    parser = argparse.ArgumentParser(description='LTP next-gen runner')
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose mode")
    parser.add_argument(
        "--suite-timeout",
        "-T",
        type=int,
        default=3600,
        help="Timeout before stopping the suite")
    parser.add_argument(
        "--exec-timeout",
        "-t",
        type=int,
        default=3600,
        help="Timeout before stopping a single execution")
    parser.add_argument(
        "--run-suite",
        "-r",
        nargs="*",
        help="Suites to run")
    parser.add_argument(
        "--run-cmd",
        "-c",
        help="Command to run")
    parser.add_argument(
        "--sut",
        "-s",
        default="host",
        type=_sut_config,
        help="System Under Test parameters")
    parser.add_argument(
        "--install",
        "-i",
        type=_install_config,
        help="LTP install configuration")
    parser.add_argument(
        "--json-report",
        "-j",
        type=str,
        help="JSON output report")

    args = parser.parse_args()

    _ltp_run(parser, args)


if __name__ == "__main__":
    run()
