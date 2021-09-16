"""
File-like trace bufffer that sends to gitlab
"""
import os
import time
from contextlib import contextmanager
from gitlabemu.ansi import ANSI_CLEAR_LINE, ANSI_CYAN, ANSI_RESET


class TraceProxy(object):
    """
    Handle sending trace from the runner to gitlab
    """

    def __init__(self, runner, job):
        self.runner = runner
        self.job = job
        self.offset = 0
        self.emulator_job = None

        self.buffer = b""
        self.last_write = 0
        self.write_interval = 2

    def _should_write(self):
        """
        Return True if we should write data to the job trace
        :param data:
        :return:
        """
        if len(self.buffer) > 1024:
            return True
        if time.time() - self.last_write > self.write_interval:
            return True
        return False

    def write(self, data, flush=False):
        """
        Log the given data to the server
        :param data:
        :param flush: write any buffered content
        :return:
        """
        if hasattr(data, "encode"):
            data = data.encode()
        self.buffer += data

        if self._should_write() or flush:
            self.flush()

    @contextmanager
    def section(self, section, header):
        start = int(time.time())
        self.writeline(f"\r{ANSI_CLEAR_LINE}section_start:{start}:{section}\r{ANSI_CLEAR_LINE}{ANSI_CYAN}{header}{ANSI_RESET}")
        yield
        ended = int(time.time())
        self.writeline(f"\r{ANSI_CLEAR_LINE}section_end:{ended}:{section}\r{ANSI_CLEAR_LINE}")

    def writeline(self, text):
        """
        Write a message on it's own line
        :param text:
        :return:
        """
        text = str(text)
        if not text.endswith(os.linesep):
            text += os.linesep
        self.write(text)

    def flush(self):
        """
        Flush the buffer
        :return:
        """
        self.offset = self.runner.trace(self, self.buffer, offset=self.offset)
        self.buffer = b""
        self.last_write = time.time()

    def close(self):
        """
        Close the buffer
        :return:
        """
        pass
