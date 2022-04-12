"""
.. module:: main
    :platform: Linux
    :synopsis: main script

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import pwd
import json
import pathlib
import argparse
import shutil
import tempfile
import logging
import logging.config
from argparse import Namespace

import ltp.install
from ltp import LTPException
from ltp.install import InstallerError
from ltp.backend import LocalBackendFactory
from ltp.backend import QemuBackendFactory
from ltp.dispatcher import SerialDispatcher
from ltp.results import SuiteResults
from ltp.results import JSONExporter


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


def _init_logging() -> None:
    """
    Initialize logging objects.
    """
    current_dir = os.path.dirname(os.path.realpath(__file__))
    logging_file = os.path.join(current_dir, "logger.json")

    with open(logging_file, 'r', encoding='UTF-8') as jsonfile:
        data = json.load(jsonfile)
        logging.config.dictConfig(data)


def _ltp_host(args: Namespace) -> None:
    """
    Handle "host" subcommand.
    """
    logger = logging.getLogger("ltp.main")

    if args.json_report and os.path.exists(args.json_report):
        logger.error("JSON report file already exists: %s", args.json_report)
        return

    ltpdir = os.environ.get("LTPROOT", "/opt/ltp")
    tmpbase = os.environ.get("TMPDIR", tempfile.gettempdir())

    dispatcher = None

    try:
        if args.list:
            runtestdir = os.path.join(ltpdir, "runtest")
            suites = [name for name in os.listdir(runtestdir)
                      if os.path.isfile(os.path.join(runtestdir, name))]

            logger.info("Available tests:\n")
            for suite in suites:
                logger.info("\t%s", suite)

            logger.info("")
        else:
            tmpdir = TempRotator(tmpbase).rotate()

            factory = LocalBackendFactory(ltpdir, tmpdir)
            dispatcher = SerialDispatcher(ltpdir, tmpdir, factory)

            results = dispatcher.exec_suites(args.run_suite)

            for result in results:
                _print_results(result)

            if args.json_report:
                exporter = JSONExporter()
                exporter.save_file(results, args.json_report)
    except LTPException as err:
        logger.error("Error: %s", str(err))
    except KeyboardInterrupt:
        if dispatcher:
            dispatcher.stop()


def _ltp_qemu(args: Namespace) -> None:
    """
    Handle "qemu" subcommand.
    """
    logger = logging.getLogger("ltp.main")

    if args.json_report and os.path.exists(args.json_report):
        logger.error("JSON report file already exists: %s", args.json_report)
        return

    ltpdir = os.environ.get("LTPROOT", "/opt/ltp")
    tmpbase = os.environ.get("TMPDIR", tempfile.gettempdir())
    tmpdir = TempRotator(tmpbase).rotate()

    dispatcher = None

    try:
        factory = QemuBackendFactory(
            ltpdir=ltpdir,
            tmpdir=tmpdir,
            image=args.image,
            image_overlay=args.image_overlay,
            password=args.password,
            system=args.system,
            ram=args.ram,
            smp=args.smp,
            serial=args.serial_type,
            ro_image=args.ro_image,
            virtfs=args.virtfs)

        dispatcher = SerialDispatcher(ltpdir, tmpdir, factory)
        results = dispatcher.exec_suites(args.run_suite)

        for result in results:
            _print_results(result)

        if args.json_report:
            exporter = JSONExporter()
            exporter.save_file(results, args.json_report)
    except LTPException as err:
        logger.error("Error: %s", str(err))
    except KeyboardInterrupt:
        if dispatcher:
            dispatcher.stop()


def _ltp_install(args: Namespace) -> None:
    """
    Handle "install" subcommand.
    """
    logger = logging.getLogger("ltp.main")

    try:
        installer = ltp.install.get_installer()
        installer.install(
            args.m32,
            args.repo_url,
            args.repo_dir,
            args.install_dir)
    except InstallerError as err:
        logger.error("Error: %s", str(err))


def run() -> None:
    """
    Entry point of the application.
    """
    _init_logging()

    parser = argparse.ArgumentParser(description='LTP next-gen runner')
    subparsers = parser.add_subparsers()

    # run subcommand parsing
    host_parser = subparsers.add_parser("host")
    host_parser.set_defaults(func=_ltp_host)
    host_parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available testing suites")
    host_parser.add_argument(
        "--run-suite",
        "-s",
        type=str,
        nargs="*",
        required=True,
        help="Run testing suites on host")
    host_parser.add_argument(
        "--json-report",
        "-j",
        type=str,
        help="JSON output report")

    # run subcommand parsing
    qemu_parser = subparsers.add_parser("qemu")
    qemu_parser.set_defaults(func=_ltp_qemu)
    qemu_parser.add_argument(
        "--image",
        "-i",
        type=str,
        required=True,
        help="Qemu image")
    qemu_parser.add_argument(
        "--image-overlay",
        "-o",
        type=str,
        help="Qemu image overlay")
    qemu_parser.add_argument(
        "--password",
        "-p",
        type=str,
        default="root",
        help="Qemu root password. Default: root")
    qemu_parser.add_argument(
        "--system",
        "-a",
        type=str,
        default="x86_64",
        help="Qemu system. Default: x86_64")
    qemu_parser.add_argument(
        "--ram",
        "-r",
        type=str,
        default="1.5G",
        help="Qemu RAM. Default: 1.5G")
    qemu_parser.add_argument(
        "--smp",
        "-c",
        type=str,
        default="2",
        help="Qemu number of CPUs. Default: 2")
    qemu_parser.add_argument(
        "--virtfs",
        "-v",
        type=str,
        default="/mnt",
        help="Path to a host folder to mount in the guest")
    qemu_parser.add_argument(
        "--ro-image",
        "-m",
        type=str,
        help="Path to an image which will be exposed as read only")
    qemu_parser.add_argument(
        "--serial-type",
        "-t",
        type=str,
        default="isa",
        help="Qemu serial protocol type. Default: isa")
    qemu_parser.add_argument(
        "--run-suite",
        "-s",
        type=str,
        nargs="*",
        required=True,
        help="Run testing suites in Qemu VM")
    qemu_parser.add_argument(
        "--json-report",
        "-j",
        type=str,
        help="JSON output report")

    # install subcommand parsing
    ins_parser = subparsers.add_parser("install")
    ins_parser.set_defaults(func=_ltp_install)
    ins_parser.add_argument(
        "repo_url",
        metavar="URL",
        type=str,
        help="URL of the LTP repository")
    ins_parser.add_argument(
        "--m32",
        "-m",
        action="store_true",
        help="Install LTP using 32bit support")
    ins_parser.add_argument(
        "--repo-dir",
        "-r",
        type=str,
        default="ltp",
        dest="repo_dir",
        help="directory where LTP repository will be cloned")
    ins_parser.add_argument(
        "--install-dir",
        "-i",
        type=str,
        default="/opt/ltp",
        dest="install_dir",
        help="directory where LTP will be installed")

    # show-deps subcommand parsing
    deps_parser = subparsers.add_parser("show-deps")
    ltp.install.init_cmdline(deps_parser)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
