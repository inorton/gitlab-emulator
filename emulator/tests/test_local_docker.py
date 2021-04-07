"""
Test using local docker
"""
import pytest
import platform
import os

from gitlabemu.runner import run
from gitlabemu.errors import DockerExecError

TOPDIR = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
TEST_DIR = os.path.join(TOPDIR, "emulator", "tests")


def test_self(linux_docker, capsys):
    """
    Test that we can do a simple build using docker
    :param linux_docker:
    :return:
    """
    run(["-c", os.path.join(TOPDIR, "test-ci.yml"),
         "--full", "linux-build-later"])

    out, err = capsys.readouterr()
    assert "SOME_VARIABLE=hello" in out


def test_self_fail(linux_docker, capsys):
    """
    Test that we can do a simple build using docker and correctly detect a failure
    :param linux_docker:
    :return:
    """
    with pytest.raises(SystemExit):
        run(["-c", os.path.join(TOPDIR, "test-ci.yml"),
             "--full", ".bad-linux-docker-job"])

    out, err = capsys.readouterr()
    assert "running build bad" in out
    assert "running after" in out


def test_no_such_exec(linux_docker, mocker, capsys):
    """
    Test that we handle docker exec "no such exec instance" errors
    :param has_docker:
    :return:
    """
    def mock_exec(_, workspace, shell, user=None):
        raise DockerExecError()

    mocker.patch("gitlabemu.helpers.DockerTool.exec", mock_exec)

    with pytest.raises(DockerExecError):
        run(["-c", os.path.join(TOPDIR, "test-ci.yml"),
             "alpine-test"])
    out, err = capsys.readouterr()
    assert "Warning: docker exec error" in out


def test_services(linux_docker, capsys):
    """
    Test that we can do a simple build using docker with services
    :param linux_docker:
    :return:
    """
    run(["-c", os.path.join(TEST_DIR, "test-services.yaml"),
         "--full", "job1"])

    out, err = capsys.readouterr()
    assert "Welcome to nginx!" in out
