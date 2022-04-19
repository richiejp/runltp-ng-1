"""
Test downloader implementations.
"""
import os
import time
import pytest
import threading
from ltp.downloader import LocalDownloader
from ltp.downloader import SCPDownloader


class _TestDownloader:
    """
    Generic Downloader test for various implementations.
    """

    @pytest.fixture
    def downloader(self):
        """
        Implement this fixture to test downloaders fetch_file method.
        """
        pass

    def test_fetch_file_bad_args(self, tmpdir, downloader):
        """
        Test fetch_file method with bad arguments.
        """
        with pytest.raises(ValueError):
            downloader.fetch_file(None, "local_file")

        target_path = tmpdir / "target_file"
        target_path.write("runltp-ng tests")
        with pytest.raises(ValueError):
            downloader.fetch_file(str(target_path), None)

        with pytest.raises(ValueError):
            downloader.fetch_file("this_file_doesnt_exist", None)

    def test_fetch_file(self, tmpdir, downloader):
        """
        Test fetch_file method.
        """
        local_path = tmpdir / "local_file"
        target_path = tmpdir / "target_file"
        target_path.write("runltp-ng tests")

        target = str(target_path)
        local = str(local_path)

        downloader.fetch_file(target, local)
        downloader.stop()

        assert os.path.isfile(local)
        assert open(target, 'r').read() == "runltp-ng tests"

    def test_stop_fetch_file(self, tmpdir, downloader):
        """
        Test stop method when running fetch_file.
        """
        local_path = tmpdir / "local_file"
        target_path = tmpdir / "target_file"

        target = str(target_path)
        local = str(local_path)

        # create a big file to have enough IO traffic and slow
        # down fetch_file() method
        with open(target, 'wb') as ftarget:
            ftarget.seek(1*1024*1024*1024-1)
            ftarget.write(b'\0')

        def _threaded():
            time.sleep(1)
            downloader.stop()

        thread = threading.Thread(target=_threaded)
        thread.start()

        downloader.fetch_file(target, local)
        thread.join()

        target_size = os.stat(target).st_size
        local_size = os.stat(local).st_size

        assert target_size != local_size


class TestLocalDownloader(_TestDownloader):
    """
    Test LocalDownloader implementation.
    """

    @pytest.fixture
    def downloader(self):
        yield LocalDownloader()


@pytest.mark.usefixtures("ssh_server")
class TestSCPDownloader(_TestDownloader):
    """
    Test SCPDownloader implementation.
    """

    @pytest.fixture(scope="module")
    def config(self):
        """
        Fixture exposing configuration
        """
        class Config:
            """
            Configuration class
            """
            import pwd
            hostname = "127.0.0.1"
            port = 2222
            testsdir = os.path.abspath(os.path.dirname(__file__))
            currdir = os.path.abspath('.')
            user = pwd.getpwuid(os.geteuid()).pw_name
            user_key = os.path.sep.join([testsdir, 'id_rsa'])
            user_key_pub = os.path.sep.join([testsdir, 'id_rsa.pub'])

        return Config()

    @pytest.fixture
    def downloader(self, config):
        yield SCPDownloader(
            host=config.hostname,
            port=config.port,
            user=config.user,
            key_file=config.user_key
        )
