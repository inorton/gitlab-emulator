"""
Test tollerance of binary data in stdout and stderr from builds
"""
import os
import sys

from gitlabemu import runner


HERE = os.path.dirname(__file__)


def test_binary_output(linux_docker, cwd):
    """
    Test we handle non-unicode data without crashing
    :param linux_docker:
    :return:
    """
    sys.stdout.reconfigure(encoding="ANSI_X3.4-1968")
    os.chdir(HERE)
    os.environ["EXECUTE_VARIABLE"] = "cat binary.txt; dd if=/dev/urandom bs=2 count=64"
    runner.run(["-c", "basic.yml", "vars-job", "--var", "EXECUTE_VARIABLE"])
