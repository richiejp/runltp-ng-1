"""
Test downloader implementations.
"""
import os
import pytest
import logging
import threading
from ltp.downloader import LocalDownloader


class TestLocalDownloader:
    """
    Test LocalDownloader implementation.
    """

    def test_fetch_file_bad_args(self, tmpdir):
        """
        Test fetch_file method with bad arguments.
        """
        obj = LocalDownloader()
        with pytest.raises(ValueError):
            obj.fetch_file(None, "local_file")

        target_path = tmpdir / "target_file"
        target_path.write("runltp-ng tests")
        with pytest.raises(ValueError):
            obj.fetch_file(target_path, None)

        with pytest.raises(ValueError):
            obj.fetch_file("this_file_doesnt_exist", None)

    def test_fetch_file(self, tmpdir):
        """
        Test fetch_file method.
        """
        local_path = tmpdir / "local_file"
        target_path = tmpdir / "target_file"
        target_path.write("runltp-ng tests")

        obj = LocalDownloader()
        obj.fetch_file(target_path, local_path)
        obj.stop()

        assert os.path.isfile(local_path)
        assert open(target_path, 'r').read() == "runltp-ng tests"

    def test_stop_fetch_file(self, tmpdir, caplog):
        """
        Test stop method when running fetch_file.
        """
        caplog.set_level(logging.INFO)

        local_path = tmpdir / "local_file"
        target_path = tmpdir / "target_file"

        # create a big file to have enough IO traffic and slow
        # down fetch_file() method
        with open(target_path, 'wb') as ftarget:
            ftarget.seek(1*1024*1024*1024-1)
            ftarget.write(b'\0')

        obj = LocalDownloader()

        thread = threading.Thread(
            target=lambda: obj.fetch_file(target_path, local_path))

        thread.start()
        obj.stop()
        thread.join()

        assert "Copy stopped" in caplog.messages
