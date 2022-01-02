"""
.. module:: report
    :platform: Linux
    :synopsis: module that contains functions to export test reports.

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import json
import logging
from .session import LTPSession


def export_to_json(session: LTPSession, output: str) -> None:
    """
    Export a list of testing suites into a JSON file.
    :param session: LTP session object
    :type session: LTPSession
    :param output: path of the file to export
    :type output: str
    """
    if not session:
        raise ValueError("session")

    if not output:
        raise ValueError("output")

    logger = logging.getLogger("ltp.report")
    logger.info("Exporting JSON report into %s", output)

    data = {}
    data['session'] = {
        "name": session.name,
        "suites": [],
        "passed": session.passed,
        "failed": session.failed,
        "warnings": session.warnings,
        "skipped": session.skipped,
        "broken": session.broken,
    }

    suites = []
    for suite in session.suites:
        if not suite.completed:
            continue

        suite_data = {
            "name": suite.name,
            "tests": [],
            "passed": suite.passed,
            "failed": suite.failed,
            "warnings": suite.warnings,
            "skipped": suite.skipped,
            "broken": suite.broken,
        }

        for test in suite.tests:
            if not test.completed:
                continue

            suite_data['tests'].append({
                "name": test.name,
                "stdout": test.stdout,
                "passed": test.passed,
                "failed": test.failed,
                "warnings": test.warnings,
                "skipped": test.skipped,
                "broken": test.broken,
            })

        suites.append(suite_data)

    data['session']['suites'] = suites

    with open(output, "w+", encoding='UTF-8') as outfile:
        json.dump(data, outfile, indent=4)

    logger.info("JSON report has been exported")
