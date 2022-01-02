"""
Unittest for report module.
"""
import json
import pytest
from ltp.session import LTPSession
from ltp.report import export_to_json


@pytest.fixture
def stdout_msg():
    def _callback(passed, failed, broken, skipped, warnings):
        msg = "\n\nSummary:\n" \
            f"passed   {passed}\n" \
            f"failed   {failed}\n" \
            f"broken   {broken}\n" \
            f"skipped  {skipped}\n" \
            f"warnings {warnings}\n"
        return msg

    return _callback


@pytest.mark.usefixtures("prepare_tmpdir")
def test_export_to_json_session_run(tmpdir, stdout_msg):
    """
    Test export_to_json function when running a session.
    """
    reportfile = tmpdir.join("report.json")

    session = LTPSession()
    session.run()

    export_to_json(session, str(reportfile))

    data = None
    with open(str(reportfile), "r") as report:
        data = json.load(report)

    assert data["session"]["name"] is not None
    assert data["session"]["passed"] == 1
    assert data["session"]["failed"] == 1
    assert data["session"]["warnings"] == 1
    assert data["session"]["broken"] == 1
    assert data["session"]["skipped"] == 1

    assert len(data["session"]["suites"]) == 5
    assert {
        "name": "dirsuite0",
        "passed": 1,
        "failed": 0,
        "warnings": 0,
        "broken": 0,
        "skipped": 0,
        "tests": [
                {
                    "name": "dir01",
                    "passed": 1,
                    "failed": 0,
                    "warnings": 0,
                    "broken": 0,
                    "skipped": 0,
                    "stdout": stdout_msg(1, 0, 0, 0, 0),
                },
        ]
    } in data["session"]["suites"]
    assert {
        "name": "dirsuite1",
        "passed": 0,
        "failed": 1,
        "warnings": 0,
        "broken": 0,
        "skipped": 0,
        "tests": [
                {
                    "name": "dir01",
                    "passed": 0,
                    "failed": 1,
                    "warnings": 0,
                    "broken": 0,
                    "skipped": 0,
                    "stdout": stdout_msg(0, 1, 0, 0, 0),
                },
        ]
    } in data["session"]["suites"]
    assert {
        "name": "dirsuite2",
        "passed": 0,
        "failed": 0,
        "warnings": 0,
        "broken": 0,
        "skipped": 1,
        "tests": [
                {
                    "name": "dir01",
                    "passed": 0,
                    "failed": 0,
                    "warnings": 0,
                    "broken": 0,
                    "skipped": 1,
                    "stdout": stdout_msg(0, 0, 0, 1, 0),
                },
        ]
    } in data["session"]["suites"]
    assert {
        "name": "dirsuite3",
        "passed": 0,
        "failed": 0,
        "warnings": 0,
        "broken": 1,
        "skipped": 0,
        "tests": [
                {
                    "name": "dir01",
                    "passed": 0,
                    "failed": 0,
                    "warnings": 0,
                    "broken": 1,
                    "skipped": 0,
                    "stdout": stdout_msg(0, 0, 1, 0, 0),
                },
        ]
    } in data["session"]["suites"]
    assert {
        "name": "dirsuite4",
        "passed": 0,
        "failed": 0,
        "warnings": 1,
        "broken": 0,
        "skipped": 0,
        "tests": [
                {
                    "name": "dir01",
                    "passed": 0,
                    "failed": 0,
                    "warnings": 1,
                    "broken": 0,
                    "skipped": 0,
                    "stdout": stdout_msg(0, 0, 0, 0, 1),
                },
        ]
    } in data["session"]["suites"]


@pytest.mark.usefixtures("prepare_tmpdir")
def test_export_to_json_session_run_scenario(tmpdir, stdout_msg):
    """
    Test export_to_json function when running a testing scenario.
    """
    reportfile = tmpdir.join("report.json")

    session = LTPSession()
    session.run_scenario("default")

    export_to_json(session, str(reportfile))

    data = None
    with open(str(reportfile), "r") as report:
        data = json.load(report)

    assert data["session"]["name"] is not None
    assert data["session"]["passed"] == 1
    assert data["session"]["failed"] == 1
    assert data["session"]["warnings"] == 0
    assert data["session"]["broken"] == 0
    assert data["session"]["skipped"] == 0

    assert len(data["session"]["suites"]) == 2
    assert {
        "name": "dirsuite0",
        "passed": 1,
        "failed": 0,
        "warnings": 0,
        "broken": 0,
        "skipped": 0,
        "tests": [
                {
                    "name": "dir01",
                    "passed": 1,
                    "failed": 0,
                    "warnings": 0,
                    "broken": 0,
                    "skipped": 0,
                    "stdout": stdout_msg(1, 0, 0, 0, 0),
                },
        ]
    } in data["session"]["suites"]
    assert {
        "name": "dirsuite1",
        "passed": 0,
        "failed": 1,
        "warnings": 0,
        "broken": 0,
        "skipped": 0,
        "tests": [
                {
                    "name": "dir01",
                    "passed": 0,
                    "failed": 1,
                    "warnings": 0,
                    "broken": 0,
                    "skipped": 0,
                    "stdout": stdout_msg(0, 1, 0, 0, 0),
                },
        ]
    } in data["session"]["suites"]


@pytest.mark.usefixtures("prepare_tmpdir")
def test_export_to_json_session_run_single(tmpdir, stdout_msg):
    """
    Test export_to_json function when running a testing scenario.
    """
    reportfile = tmpdir.join("report.json")

    session = LTPSession()
    session.run(suites=["dirsuite0"])

    export_to_json(session, str(reportfile))

    data = None
    with open(str(reportfile), "r") as report:
        data = json.load(report)

    assert data["session"]["name"] is not None
    assert data["session"]["passed"] == 1
    assert data["session"]["failed"] == 0
    assert data["session"]["warnings"] == 0
    assert data["session"]["broken"] == 0
    assert data["session"]["skipped"] == 0

    assert len(data["session"]["suites"]) == 1
    assert {
        "name": "dirsuite0",
        "passed": 1,
        "failed": 0,
        "warnings": 0,
        "broken": 0,
        "skipped": 0,
        "tests": [
            {
                "name": "dir01",
                "passed": 1,
                "failed": 0,
                "warnings": 0,
                "broken": 0,
                "skipped": 0,
                "stdout": stdout_msg(1, 0, 0, 0, 0),
            }
        ]
    } in data["session"]["suites"]
