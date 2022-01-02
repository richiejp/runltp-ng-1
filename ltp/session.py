"""
.. module:: session
    :platform: Linux
    :synopsis: module that contains session/suite and test definitions

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import re
import logging
import subprocess
from datetime import datetime


class LTPTestError(Exception):
    """
    Raised during a test execution when an error occurs.
    """


class LTPObject:
    """
    A generic class to inherit in order to get LTP information, such as
    directories, tests reports, etc.
    """

    def __init__(self) -> None:
        self._root_dir = None
        self._runtest_dir = None
        self._scenario_dir = None
        self._testcases_dir = None
        self._tmp_dir = None
        self._completed = False
        self.refresh_env()

    def refresh_env(self):
        """
        Refresh object according with environment variables.
        """
        self._root_dir = os.environ.get(
            "LTPROOT", os.path.dirname(os.path.abspath(__file__)))
        self._runtest_dir = os.path.join(self._root_dir, "runtest")
        self._scenario_dir = os.path.join(self._root_dir, "scenario_groups")
        self._testcases_dir = os.path.join(self._root_dir, "testcases", "bin")
        self._tmp_dir = os.environ.get("TMPDIR", None)
        self._completed = False

    @property
    def completed(self) -> bool:
        """
        True if test/suite/session has been completed.
        """
        return self._completed

    @property
    def failed(self) -> int:
        """
        Number of TFAIL.
        :returns: int
        """
        raise NotImplementedError()

    @property
    def passed(self) -> int:
        """
        Number of TPASS.
        :returns: int
        """
        raise NotImplementedError()

    @property
    def broken(self) -> int:
        """
        Number of TBROK.
        :returns: int
        """
        raise NotImplementedError()

    @property
    def skipped(self) -> int:
        """
        Number of TSKIP.
        :returns: int
        """
        raise NotImplementedError()

    @property
    def warnings(self) -> int:
        """
        Number of TWARN.
        :returns: int
        """
        raise NotImplementedError()


class LTPSession(LTPObject):
    """
    LTP session abstraction class.
    """

    def __init__(self) -> None:
        super().__init__()

        self._logger = logging.getLogger("ltp.session")
        self._name = datetime.now().strftime("LTP_%Y_%m_%d-%Hh_%Mm_%Ss")
        self._suites = self._collect_suites()

        self._logger.debug(
            "name=%s, ltproot=%s, runtest=%s, testcases=%s",
            self._name,
            self._root_dir,
            self._runtest_dir,
            self._testcases_dir)

    def _collect_suites(self) -> list:
        """
        Collect all the available testing suites.
        """
        suites = []

        self._logger.debug("collecting suites")

        files = [os.path.join(self._runtest_dir, fname)
                 for fname in os.listdir(self._runtest_dir)
                 if os.path.isfile(os.path.join(self._runtest_dir, fname))]

        for fpath in files:
            suite = LTPSuite(fpath)
            suites.append(suite)

        self._logger.debug("collected %d suites", len(suites))

        return suites

    @property
    def name(self) -> str:
        """
        Name of the session, which is the composition of prefix and date in the
        form of "LTP_%Y_%m_%d-%Hh_%Mm_%Ss".
        :returns: str
        """
        return self._name

    @property
    def suites(self) -> list:
        """
        List  of suites for this session.
        :returns: list(Suite)
        """
        return self._suites

    def _get_result(self, attr: str) -> int:
        """
        Return the total number of results.
        """
        res = 0
        for suite in self._suites:
            res += getattr(suite, attr)

        return res

    @property
    def failed(self) -> int:
        """
        Number of TFAIL.
        :returns: int
        """
        return self._get_result("failed")

    @property
    def passed(self) -> int:
        """
        Number of TPASS.
        :returns: int
        """
        return self._get_result("passed")

    @property
    def broken(self) -> int:
        """
        Number of TBROK.
        :returns: int
        """
        return self._get_result("broken")

    @property
    def skipped(self) -> int:
        """
        Number of TSKIP.
        :returns: int
        """
        return self._get_result("skipped")

    @property
    def warnings(self) -> int:
        """
        Number of TWARN.
        :returns: int
        """
        return self._get_result("warnings")

    def suites_from_scenario(self, scenario: str = "all") -> list:
        """
        List  of suites names inside a specific scenario.
        :param scenario: name of the scenario ["all", "default", "network"]
        :type scenario: str
        :returns: list(str)
        """
        suites = []

        if scenario in ["default", "network"]:
            suites_file = os.path.join(
                self._root_dir,
                "scenario_groups",
                scenario)

            if not os.path.isfile(suites_file):
                raise ValueError(f"{suites_file} doesn't exist")

            names = []
            with open(suites_file, "r", encoding='UTF-8') as data:
                for line in data:
                    names.append(line.rstrip())

            suites = [suite for suite in self._suites if suite.name in names]
        else:
            suites = self._suites

        return suites

    def run_scenario(self, scenario: str = "all") -> list:
        """
        Run a specific scenario.
        :param scenario: name of the scenario ["all", "default", "network"]
        :type scenario: str
        :returns: list of suites which have been run as list(LTPSuite)
        :raises: LTPTestError
        """
        if scenario and scenario not in ["all", "default", "network"]:
            raise ValueError("scenario must be 'default', 'network' or 'all'")

        self._logger.debug("collecting suites from '%s' scenario", scenario)

        try:
            suites = self.suites_from_scenario(scenario)
            for suite in suites:
                suite.run()
        finally:
            self._completed = True

        return suites

    def run(self, suites: list = None) -> list:
        """
        Run given test suites. If suites is None, "default" scenario will run.
        :param suites: list of testing suites to execute
        :type suites: list
        :returns: list of suites which have been run as list(LTPSuite)
        :raises: LTPTestError
        """
        self._logger.debug("running suites=%s", suites)

        suites2run = None
        if not suites:
            suites2run = self._suites
        else:
            suites2run = [
                suite for suite in self._suites
                if suite.name in suites]

        try:
            for suite in suites2run:
                suite.run()
        finally:
            self._completed = True

        return suites2run


class LTPSuite(LTPObject):
    """
    LTP testing suite abstraction class.
    """

    def __init__(self, path: str) -> None:
        """
        :param path: abs path of the testing suite file declaration
        :type path: str
        """
        if not path:
            raise ValueError("path is empty")

        if not os.path.isfile(path):
            raise ValueError(f"{path} is not a file")

        super().__init__()

        self._logger = logging.getLogger("ltp.suite")
        self._name = os.path.basename(path)
        self._tests = self._tests_from_path(path)

    def _tests_from_path(self, path: str) -> list:
        """
        Return a list of LTPTests from a testing suite declaration.
        """
        self._logger.debug("collecting tests")

        tests = []
        with open(path, "r", encoding='UTF-8') as data:
            for line in data:
                if not line.strip() or line.strip().startswith("#"):
                    continue

                test = LTPTest(line)
                tests.append(test)

        self._logger.debug("collected %d tests", len(tests))

        return tests

    @property
    def name(self) -> str:
        """
        Name of the testing suite.
        :returns: str
        """
        return self._name

    @property
    def tests(self) -> list:
        """
        List of the tests inside the suite.
        :returns: list(LTPTest)
        """
        return self._tests

    def _get_result(self, attr: str) -> int:
        """
        Return the total number of results.
        """
        res = 0
        for test in self._tests:
            res += getattr(test, attr)

        return res

    @property
    def failed(self) -> int:
        """
        Number of TFAIL.
        :returns: int
        """
        return self._get_result("failed")

    @property
    def passed(self) -> int:
        """
        Number of TPASS.
        :returns: int
        """
        return self._get_result("passed")

    @property
    def broken(self) -> int:
        """
        Number of TBROK.
        :returns: int
        """
        return self._get_result("broken")

    @property
    def skipped(self) -> int:
        """
        Number of TSKIP.
        :returns: int
        """
        return self._get_result("skipped")

    @property
    def warnings(self) -> int:
        """
        Number of TWARN.
        :returns: int
        """
        return self._get_result("warnings")

    def run(self) -> None:
        """
        Run all tests inside the suite.
        :raises: LTPTestError
        """
        try:
            for test in self._tests:
                try:
                    test.run()
                except LTPTestError as err:
                    self._logger.error(str(err))
        finally:
            self._completed = True


class LTPTest(LTPObject):
    """
    LTP test abstraction class.
    """

    def __init__(self, decl: str) -> None:
        """
        :param decl: declaration line from test suite file
        :type decl: str
        """
        if not decl:
            raise ValueError("empty test declaration")

        super().__init__()

        data = self._from_declaration(decl)

        self._name = data["name"]
        self._command = data["cmd"]
        self._args = data["args"]
        self._pass = 0
        self._fail = 0
        self._brok = 0
        self._skip = 0
        self._warn = 0
        self._stdout = ""

        self._logger = logging.getLogger("ltp.test")
        self._logger.debug(
            "name: %s, command: %s, args: %s",
            self._name,
            self._command,
            self._args)

    @staticmethod
    def _from_declaration(decl: str) -> dict:
        """
        Return a dictionary containing test name, command and arguments.
        """
        parts = decl.split()
        if len(parts) < 2:
            raise ValueError("Test declaration is bad defined")

        data = dict(
            name=parts[0],
            cmd=parts[1],
            args=[]
        )

        if len(parts) >= 3:
            data["args"] = parts[2:]

        return data

    @property
    def name(self) -> str:
        """
        Name of the test.
        :returns: str
        """
        return self._name

    @property
    def command(self) -> str:
        """
        Command of the test.
        :returns: str
        """
        return self._command

    @property
    def args(self) -> list:
        """
        Arguments of the command.
        :returns: list(str)
        """
        return self._args

    @property
    def failed(self) -> int:
        """
        Number of TFAIL.
        :returns: int
        """
        return self._fail

    @property
    def passed(self) -> int:
        """
        Number of TPASS.
        :returns: int
        """
        return self._pass

    @property
    def broken(self) -> int:
        """
        Number of TBROK.
        :returns: int
        """
        return self._brok

    @property
    def skipped(self) -> int:
        """
        Number of TSKIP.
        :returns: int
        """
        return self._skip

    @property
    def warnings(self) -> int:
        """
        Number of TWARN.
        :returns: int
        """
        return self._warn

    @property
    def stdout(self) -> str:
        """
        Test stdout.
        :returns: str
        """
        return self._stdout

    def run(self) -> None:
        """
        Run the test.
        :raises: LTPTestError
        """
        self.refresh_env()

        env = {}
        env["LTPROOT"] = self._root_dir
        if self._tmp_dir:
            env["TMPDIR"] = self._tmp_dir

        # enable colors
        env["LTP_COLORIZE_OUTPUT"] = os.environ.get("LTP_COLORIZE_OUTPUT", "y")

        # PATH must be set in order to run bash scripts
        env["PATH"] = f'{os.environ.get("PATH")}:{self._testcases_dir}'

        cmd = f'{self._command} {" ".join(self._args)}'

        self._logger.debug("start running command: '%s'", cmd)

        # keep usage of preexec_fn trivial
        # see warnings in https://docs.python.org/3/library/subprocess.html
        # pylint: disable=subprocess-popen-preexec-fn
        with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self._root_dir,
                env=env,
                shell=True,
                universal_newlines=True,
                preexec_fn=os.setsid) as proc:

            for line in iter(proc.stdout.readline, b''):
                if not line:
                    break

                self._logger.info(line.rstrip())
                self._stdout += line

            proc.wait()

            self._completed = True

            match = re.search(
                r"Summary:\n"
                r"passed\s*(?P<passed>\d+)\n"
                r"failed\s*(?P<failed>\d+)\n"
                r"broken\s*(?P<broken>\d+)\n"
                r"skipped\s*(?P<skipped>\d+)\n"
                r"warnings\s*(?P<warnings>\d+)\n",
                self._stdout
            )

            if match:
                self._pass = int(match.group("passed"))
                self._fail = int(match.group("failed"))
                self._skip = int(match.group("skipped"))
                self._brok = int(match.group("broken"))
                self._skip = int(match.group("skipped"))
                self._warn = int(match.group("warnings"))

                if proc.returncode != 0:
                    raise LTPTestError(f"return code: {proc.returncode}")
            else:
                # if no results are given, this is probably an
                # old test implementation that fails when return code is != 0
                self._logger.debug("detected an old style test implementation")

                if proc.returncode != 0:
                    self._fail = 1
                else:
                    self._pass = 1
