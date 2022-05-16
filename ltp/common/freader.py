"""
.. module:: freader
    :platform: Linux
    :synopsis: module containing reader for IO

.. moduleauthor:: Andrea Cervesato <andrea.cervesato@suse.com>
"""
import os
import time
import select
import threading


class IOReader:
    """
    A helper class to read IO buffers.
    """

    def __init__(self, fdesc: int) -> None:
        """
        :param fdesc: file descriptor of the stdout. It can be taken
            by using fileno()
        :type fdesc: int
        """
        self._fdesc = fdesc
        self._poller = select.epoll()
        self._poller.register(self._fdesc, select.EPOLLIN)
        self._stop_lock = threading.Lock()
        self._read_lock = threading.Lock()
        self._stop = False

    def stop(self) -> None:
        """
        Stop reading the poll.
        """
        with self._stop_lock:
            self._stop = True

            try:
                self._poller.unregister(self._fdesc)
            except OSError:
                # proc has been already closed
                # so file descriptor is not valid
                pass

            self._poller.close()

    def read_until(
            self,
            checker: callable,
            t_start: int,
            timeout: int,
            line_callback: callable = None) -> str:
        """
        Read from stdout until `checker` returns True. Method reaches `timeout`
        from `t_start` and it returns `None`.
        :param checker: callback that checks the current buffer and return True
            if inner statement is valid
        :type checker: callable
        :param t_start: time where we start to count
        :type t_start: int
        :param timeout: timeout in seconds
        :type timeout: int
        :param line_callback: called when a newline has been found
        :type line_callback: callable
        :returns: str
        """
        if not checker:
            raise ValueError("checker")

        self._stop = False

        buffer = ""

        with self._read_lock:
            line = ""
            found = False
            t_start = max(0, t_start)
            timeout = max(0, timeout)

            while not found:
                if self._stop:
                    return None

                if time.time() - t_start >= timeout:
                    return None

                # during stop poller might be closed
                if not self._poller.closed:
                    events = self._poller.poll(1)

                    for fdesc, _ in events:
                        if fdesc != self._fdesc:
                            continue

                        data = os.read(self._fdesc, 1).decode(
                            encoding='utf-8',
                            errors='ignore')

                        buffer += data
                        line += data

                        if data == '\n' and line_callback:
                            line_callback(line.rstrip())
                            line = ""

                        if checker(buffer):
                            found = True
                            break

        return buffer
