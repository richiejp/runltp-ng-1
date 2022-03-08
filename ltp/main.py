"""
.. module:: main
    :platform: Linux
    :synopsis: main script

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import logging
import logging.config
import json
import argparse
import platform
from argparse import Namespace

from .install import install_run
from .report import export_to_json
from .install import Installer
from .session import LTPSession


def _print_results(session: LTPSession) -> None:
    """
    Print session results.
    """
    logger = logging.getLogger("ltp.main")

    tests = 0
    for suite in session.suites:
        if suite.completed:
            for test in suite.tests:
                if test.completed:
                    tests += 1

    kernver = platform.uname().release
    arch = platform.architecture()[0]
    hostname = platform.uname().node

    logger.info("")
    logger.info("Total Run: %d", tests)
    logger.info("Total Passed Tests: %d", session.passed)
    logger.info("Total Failed Tests: %d", session.failed)
    logger.info("Total Skipped Tests: %d", session.skipped)
    logger.info("Total Broken Tests: %d", session.broken)
    logger.info("Total Warnings: %d", session.warnings)
    logger.info("Kernel Version:: %s", kernver)
    logger.info("Machine Architecture: %s", arch)
    logger.info("Hostname: %s", hostname)
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


def _ltp_list(args: Namespace) -> None:
    """
    Handle "list" subcommand.
    """
    session = LTPSession()
    suites = []

    if args.default:
        suites = session.suites_from_scenario(scenario="default")
    elif args.network:
        suites = session.suites_from_scenario(scenario="network")
    else:
        suites = session.suites_from_scenario()

    logger = logging.getLogger("ltp.main")
    logger.info("Testing suites:\n")
    for suite in suites:
        logger.info("\t%s", suite.name)
    logger.info("")


def _ltp_run(args: Namespace) -> None:
    """
    Handle "run" subcommand.
    """
    session = LTPSession()

    if args.default:
        session.run_scenario(scenario="default")
    elif args.network:
        session.run_scenario(scenario="network")
    elif args.all:
        session.run()
    elif args.suites:
        session.run(args.suites)

    _print_results(session)

    if args.json_report:
        export_to_json(session, args.json_report)


def _ltp_install(args: Namespace) -> None:
    """
    Handle "install" subcommand.
    """
    installer = Installer()
    installer.install(
        args.repo_url,
        args.repo_dir,
        args.install_dir)


def run() -> None:
    """
    Entry point of the application.
    """
    _init_logging()

    parser = argparse.ArgumentParser(description='LTP next-gen runner')
    subparsers = parser.add_subparsers()

    # run subcommand parsing
    run_parser = subparsers.add_parser("run")
    run_parser.set_defaults(func=_ltp_run)
    run_parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="run all test suites")
    run_parser.add_argument(
        "--default",
        "-d",
        action="store_true",
        help="run default testing scenario")
    run_parser.add_argument(
        "--network",
        "-n",
        action="store_true",
        help="run network testing scenario")
    run_parser.add_argument(
        "--suites",
        "-s",
        type=str,
        nargs="*",
        help="testing suites to run")
    run_parser.add_argument(
        "--json-report",
        "-j",
        type=str,
        help="JSON output report")

    # list subcommand parsing
    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(func=_ltp_list)
    list_parser.add_argument(
        "--default",
        "-d",
        action="store_true",
        help="list default testing scenario")
    list_parser.add_argument(
        "--network",
        "-n",
        action="store_true",
        help="list network testing scenario")

    # install subcommand parsing
    ins_parser = subparsers.add_parser("install")
    ins_parser.set_defaults(func=_ltp_install)
    ins_parser.add_argument(
        "repo_url",
        metavar="URL",
        type=str,
        help="URL of the LTP repository")
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
    deps_parser.set_defaults(func=install_run)
    deps_parser.add_argument(
        "--distro",
        metavar="DISTRO_ID",
        type=str,
        default="",
        help="Linux distribution name in the /etc/os-release ID format")
    deps_parser.add_argument(
        "--m32",
        action="store_true",
        help="Show 32 bits packages")
    deps_parser.add_argument(
        "--build",
        action="store_true",
        help="Include build packages")
    deps_parser.add_argument(
        "--runtime",
        action="store_true",
        help="Include runtime packages")

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
