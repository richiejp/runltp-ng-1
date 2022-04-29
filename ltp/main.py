"""
.. module:: main
    :platform: Linux
    :synopsis: main script

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import pwd
import pathlib
import argparse
import shutil
import tempfile
import logging
import logging.config
from argparse import ArgumentParser
from argparse import Namespace

from ltp import LTPException
from ltp.sut import LocalSUTFactory
from ltp.sut import QemuSUTFactory
from ltp.sut import SUTFactory
from ltp.sut import SSHSUTFactory
from ltp.dispatcher import SerialDispatcher
from ltp.results import SuiteResults
from ltp.results import JSONExporter
from ltp.common.events import Events
from ltp.ui import SimpleConsoleEvents


class TempRotator:
    """
    Temporary directory rotation class.
    """
    SYMLINK_NAME = "latest"

    def __init__(self, root: str, max_rotate: int = 5) -> None:
        """
        :param root: root temporary path
        :type root: str
        :param max_rotate: maximum number of rotations
        :type max_rotate: int
        """
        if not os.path.isdir(root):
            raise ValueError("root is empty")

        name = pwd.getpwuid(os.getuid()).pw_name
        self._tmpbase = os.path.join(root, f"runltp-of-{name}")
        self._max_rotate = max(max_rotate, 0)

    def rotate(self) -> str:
        """
        Check for old folders and remove them, then create a new one and return
        its full path.
        """
        os.makedirs(self._tmpbase, exist_ok=True)

        # delete the first max_rotate items
        sorted_paths = sorted(
            pathlib.Path(self._tmpbase).iterdir(),
            key=os.path.getmtime)

        # don't consider latest symlink
        num_paths = len(sorted_paths) - 1

        if num_paths >= self._max_rotate:
            max_items = num_paths - self._max_rotate + 1
            paths = sorted_paths[:max_items]

            for path in paths:
                if path.name == self.SYMLINK_NAME:
                    continue

                shutil.rmtree(str(path.resolve()))

        # create a new folder
        folder = tempfile.mkdtemp(dir=self._tmpbase)

        # create symlink to the latest temporary directory
        latest = os.path.join(self._tmpbase, self.SYMLINK_NAME)
        if os.path.islink(latest):
            os.remove(latest)

        os.symlink(
            folder,
            os.path.join(self._tmpbase, self.SYMLINK_NAME),
            target_is_directory=True)

        return folder


def _print_results(suite_results: SuiteResults) -> None:
    """
    Print suite results.
    """
    logger = logging.getLogger("ltp.main")

    tests = len(suite_results.tests_results)

    logger.info("")
    logger.info("Suite name: %s", suite_results.suite.name)
    logger.info("Total Run: %d", tests)
    logger.info("Elapsed time: %.1f seconds", suite_results.exec_time)
    logger.info("Total Passed Tests: %d", suite_results.passed)
    logger.info("Total Failed Tests: %d", suite_results.failed)
    logger.info("Total Skipped Tests: %d", suite_results.skipped)
    logger.info("Total Broken Tests: %d", suite_results.broken)
    logger.info("Total Warnings: %d", suite_results.warnings)
    logger.info("Kernel Version: %s", suite_results.kernel)
    logger.info("Machine Architecture: %s", suite_results.arch)
    logger.info("Distro: %s", suite_results.distro)
    logger.info("Distro version: %s", suite_results.distro_ver)
    logger.info("")


def _setup_debug_log(tmpdir: str) -> None:
    """
    Save a log file with debugging information
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    debug_file = os.path.join(tmpdir, "debug.log")
    handler = logging.FileHandler(debug_file, encoding="utf8")
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def _get_ui_events(args: Namespace) -> Events:
    """
    Return user interface events handler.
    """
    console = SimpleConsoleEvents(args.verbose)
    return console


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

    defaults = {
        'image',
        'image_overlay',
        'password',
        'system',
        'ram',
        'smp',
        'serial',
        'ro_image',
        'virtfs'
    }

    if not set(config).issubset(defaults):
        raise argparse.ArgumentTypeError(
            "Some parameters are not supported. "
            f"Please use the following: {', '.join(defaults)}")

    return config


def _get_ssh_config(params: list) -> dict:
    """
    Return the SSH SUT configuration.
    """
    config = _from_params_to_config(params)

    if 'host' not in config:
        raise argparse.ArgumentTypeError(
            "'host' parameter is required by qemu SUT")

    defaults = {
        'host',
        'port',
        'user',
        'password',
        'key_file',
        'timeout',
    }

    if not set(config).issubset(defaults):
        raise argparse.ArgumentTypeError(
            "Some parameters are not supported. "
            f"Please use the following: {', '.join(defaults)}")

    return config


def _sut_config(value: str) -> dict:
    """
    Return a SUT configuration according with input string.
    Format for value is, for example:

        qemu:ram=4G:smp=4:image=/local/vm.qcow2:virtfs=/opt/ltp:password=123

    """
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

        mysite.com/repo.git:commit=8f308953c60cdd25e372e8c58a3c963ab98be276

    """
    if not value:
        raise argparse.ArgumentTypeError("Install parameters can't be empty")

    params = value.split(':')
    repo = params[0]
    if '=' in repo:
        raise argparse.ArgumentTypeError(
            "First --install element must be the repository URL")

    config = _from_params_to_config(params[1:])

    defaults = {
        'commit',
        'branch',
        'm32',
        'repo_dir',
        'install_dir',
    }

    if not set(config).issubset(defaults):
        raise argparse.ArgumentTypeError(
            "Some parameters are not supported. "
            f"Please use the following: {', '.join(defaults)}")

    config['repo'] = repo

    return config


def _run_suites(args: Namespace, factory: SUTFactory, tmpdir: str) -> None:
    """
    Run given suites.
    """
    events = _get_ui_events(args)

    ltpdir = os.environ.get("LTPROOT", "/opt/ltp")
    _setup_debug_log(tmpdir)

    try:
        dispatcher = SerialDispatcher(ltpdir, tmpdir, factory, events)
        results = dispatcher.exec_suites(args.run_suite)

        if results:
            for result in results:
                _print_results(result)

            if args.json_report:
                exporter = JSONExporter()
                exporter.save_file(results, args.json_report)
    except LTPException as err:
        logger = logging.getLogger("ltp.main")
        logger.error("Error: %s", str(err))


def _ltp_run(parser: ArgumentParser, args: Namespace) -> None:
    """
    Handle runltp-ng command options.
    """
    if args.json_report and os.path.exists(args.json_report):
        parser.error(f"JSON report file already exists: {args.json_report}")

    # create temporary directory
    ltpdir = os.environ.get("LTPROOT", "/opt/ltp")
    tmpbase = os.environ.get("TMPDIR", tempfile.gettempdir())
    tmpdir = TempRotator(tmpbase).rotate()

    _setup_debug_log(tmpdir)

    # create SUT factory
    sut_factory = None

    if args.sut:
        config = args.sut
        config['ltpdir'] = ltpdir
        config['tmpdir'] = tmpdir
        name = config['name']

        if name == 'qemu':
            sut_factory = QemuSUTFactory(**args.sut)
        elif name == 'ssh':
            sut_factory = SSHSUTFactory(**args.sut)
        else:
            raise parser.error(f"'{name}' SUT is not supported")
    else:
        # default SUT is local host
        sut_factory = LocalSUTFactory()

    # create dispatcher and run tests
    _run_suites(args, sut_factory, tmpdir)


def run() -> None:
    """
    Entry point of the application.
    """
    parser = argparse.ArgumentParser(description='LTP next-gen runner')
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose mode"
    )
    parser.add_argument(
        "--run-suite",
        "-r",
        nargs="*",
        required=True,
        help="Suites to run")
    parser.add_argument(
        "--sut",
        "-s",
        type=_sut_config,
        help="System Under Test parameters")
    parser.add_argument(
        "--json-report",
        "-j",
        type=str,
        help="JSON output report")

    args = parser.parse_args()

    _ltp_run(parser, args)


if __name__ == "__main__":
    run()
