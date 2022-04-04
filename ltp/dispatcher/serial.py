"""
.. module:: serial
    :platform: Linux
    :synopsis: module containing serial dispatcher implementation

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
from ltp.backend import BackendFactory
from ltp.metadata import RuntestMetadata
from ltp.metadata.base import MetadataError
from .base import SuiteResults
from .base import Dispatcher


class SerialDispatcher(Dispatcher):
    """
    A dispatcher that serially runs jobs.
    """

    def __init__(
            self,
            ltpdir: str,
            tmpdir: str,
            backend_factory: BackendFactory) -> None:
        """
        :param ltpdir: LTP install directory
        :type ltpdir: str
        :param tmpdir: session temporary directory
        :type tmpdir: str
        :param backend_factory: backend factory object
        :type backend_factory: BackendFactory
        """
        self._ltpdir = ltpdir
        self._tmpdir = tmpdir
        self._is_running = False
        self._stop = False
        self._backend_factory = backend_factory
        self._metadata = RuntestMetadata()

        if not self._tmpdir or not os.path.isdir(self._tmpdir):
            raise ValueError("Temporary directory doesn't exist")

        if not self._backend_factory:
            raise ValueError("Backend factory is empty")

    @property
    def available_suites(self) -> list:
        runtest_dir = os.path.join(self._ltpdir, "runtest")

        suites = []
        files = [os.path.join(runtest_dir, fname)
                 for fname in os.listdir(runtest_dir)
                 if os.path.isfile(os.path.join(runtest_dir, fname))]

        for fsuite in files:
            try:
                suite = self._metadata.read_suite(fsuite)
                if suite:
                    name = os.path.basename(fsuite)
                    suites.append(name)
            except MetadataError:
                continue

        return suites

    @property
    def is_running(self) -> bool:
        return self._is_running

    def stop(self) -> None:
        self._stop = True

    # pylint: disable=too-many-locals
    def exec_suites(self, suites: list) -> list:
        if not suites:
            raise ValueError("suites list is empty")

        # create temporary directory where saving suites files
        tmp_suites = os.path.join(self._tmpdir, "suites")
        if not os.path.isdir(tmp_suites):
            os.mkdir(tmp_suites)

        self._is_running = True
        results = []

        try:
            for suite_name in suites:
                if self._stop:
                    break

                backend = self._backend_factory.create()
                downloader, runner = backend.communicate()

                # download testing suite inside temporary directory
                # TODO: handle different metadata
                target = os.path.join(self._ltpdir, "runtest", suite_name)
                local = os.path.join(tmp_suites, suite_name)
                downloader.fetch_file(target, local)

                # convert testing suites files
                suite = self._metadata.read_suite(local)

                # execute tests
                tests_results = []
                runner.start()

                for test in suite.tests:
                    if self._stop:
                        runner.stop()
                        break

                    args = " ".join(test.arguments)
                    cmd = f"{test.command} {args}"

                    # TODO: set specific timeout for each test?
                    test_data = runner.run_cmd(cmd, 3600)
                    test_results = self._get_test_results(test, test_data)
                    tests_results.append(test_results)

                # create suite results
                suite_results = SuiteResults(suite=suite, tests=tests_results)
                results.append(suite_results)
        finally:
            self._is_running = False
            self._stop = False

        return results
