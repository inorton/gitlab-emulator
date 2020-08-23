"""
Test using local docker
"""
import pytest
import platform
import os

from gitlabemu.runner import run
from gitlabemu.errors import DockerExecError


TOPDIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def test_self(has_docker, capsys):
    """
    Test that we can do a simple build using docker
    :param has_docker:
    :return:
    """
    if not platform.system() == "Linux":
        pytest.skip("Linux only")

    run(["-c", os.path.join(TOPDIR, "test-ci.yml"),
         "--full", "linux-build-later"])

    out, err = capsys.readouterr()
    assert "CI_JOB_IMAGE=ubuntu:18.04" in out


def test_no_such_exec(has_docker, mocker, capsys):
    """
    Test that we handle docker exec "no such exec instance" errors
    :param has_docker:
    :return:
    """
    def mock_exec(_, workspace, shell):
        raise DockerExecError()

    mocker.patch("gitlabemu.helpers.DockerTool.exec", mock_exec)

    with pytest.raises(DockerExecError):
        run(["-c", os.path.join(TOPDIR, "test-ci.yml"),
             "ubuntu-test"])
    out, err = capsys.readouterr()
    assert "Warning: docker exec error" in out
