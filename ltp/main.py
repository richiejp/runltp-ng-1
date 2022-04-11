"""
.. module:: main
    :platform: Linux
    :synopsis: main script

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import json
import argparse
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
    ltpdir = os.environ.get("LTPROOT", "/opt/ltp")
    tmpdir = os.environ.get("TMPDIR", tempfile.mktemp(prefix="runltp-"))
    if not os.path.isdir(tmpdir):
        os.mkdir(tmpdir)

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


def _ltp_qemu(args: Namespace) -> None:
    """
    Handle "qemu" subcommand.
    """
    logger = logging.getLogger("ltp.main")
    if not args.image:
        logger.error("No image is given. Please use --image option.")
        return

    ltpdir = os.environ.get("LTPROOT", "/opt/ltp")
    tmpdir = os.environ.get("TMPDIR", tempfile.mktemp(prefix="runltp-"))
    if not os.path.isdir(tmpdir):
        os.mkdir(tmpdir)

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
            serial=args.serial_type)

        dispatcher = SerialDispatcher(ltpdir, tmpdir, factory)
        results = dispatcher.exec_suites(args.run_suite)

        for result in results:
            _print_results(result)

        if args.json_report:
            exporter = JSONExporter()
            exporter.save_file(results, args.json_report)
    except LTPException as err:
        logger.error("Error: %s", str(err))


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
