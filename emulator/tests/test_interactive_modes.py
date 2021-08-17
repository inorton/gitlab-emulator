"""
Test -i and --before-script
"""
import os
import sys

import pytest

from gitlabemu import runner

HERE = os.path.dirname(__file__)
TOPDIR = os.path.abspath(os.path.dirname(os.path.dirname(HERE)))
TOPCFG = os.path.join(TOPDIR, ".gitlab-ci.yml")


def test_interactive_starts_before(linux_docker, capfd):
    if not sys.stdout.isatty():
        pytest.skip("tty required")
    runner.run(["-i", "-b", "-c", TOPCFG, ".check-interactive"])
    stdout, stderr = capfd.readouterr()

    assert "hello-stderr" in stderr
    assert "Running before_script.." in stdout
    assert "CI_FOO=hello" in stdout
    assert "++ done ++" in stdout
    assert "Exiting shell" in stdout


def test_interactive_starts(linux_docker, capfd):
    if not sys.stdout.isatty():
        pytest.skip("tty required")
    runner.run(["-i", "-c", TOPCFG, ".check-interactive"])
    stdout, stderr = capfd.readouterr()

    assert "hello-stderr" not in stderr
    assert "Running before_script.." not in stdout
    assert "Exiting shell" in stdout


def test_chdir(posix_only, capsys):
    os.chdir(HERE)
    topdir = os.path.dirname(TOPCFG)
    runner.run(["-l", "-C", topdir])
    stdout, stderr = capsys.readouterr()

    assert "check-alpine" in stdout


def test_chdir_nodir(posix_only, capsys):
    with pytest.raises(SystemExit):
        runner.run(["-l", "-C", "/not-a-real-dir"])
    stdout, stderr = capsys.readouterr()

    assert "Cannot change to /not-a-real-dir" in stderr


def test_noconfig(posix_only, capsys):
    os.chdir(HERE)
    with pytest.raises(SystemExit):
        runner.run(["-l"])
    stdout, stderr = capsys.readouterr()

    assert ".gitlab-ci.yml not found" in stderr
    assert "Found config:"
    assert "Please re-run from " in stderr
