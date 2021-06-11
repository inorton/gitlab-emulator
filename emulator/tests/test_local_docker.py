"""
Test using local docker
"""
import shutil
import sys
import tempfile

import pytest
import uuid
import os

from gitlabemu.helpers import ProcessLineProxyThread
from gitlabemu.runner import run
from gitlabemu.errors import DockerExecError
from gitlabemu.docker import DockerJob

TOPDIR = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
TEST_DIR = os.path.join(TOPDIR, "emulator", "tests")


def test_variables_var(linux_docker, capsys):
    """
    Test --var
    :param linux_docker:
    :param capsys:
    :return:
    """
    random_uuid1 = str(uuid.uuid4())
    random_uuid2 = str(uuid.uuid4())
    random_uuid3 = str(uuid.uuid4())

    os.environ["X_FEED_VARIABLE"] = random_uuid3
    os.environ["TOPGUN_MAV"] = "I feel the need..."
    os.environ["TOPGUN_GOOSE"] = "... the need for speed!"
    os.environ["TOPGUN"] = "F14"

    run(["-c", os.path.join(TOPDIR, "test-ci.yml"), "alpine-test",
         "--var", f"MOOSE={random_uuid1}",
         "--var", f"BADGER={random_uuid2}",
         "--var", "X_FEED_VARIABLE",
         "--revar", "^TOPGUN_"
         ])

    out, err = capsys.readouterr()
    assert f"MOOSE={random_uuid1}" in out
    assert f"BADGER={random_uuid2}" in out
    assert f"X_FEED_VARIABLE={random_uuid3}" in out

    assert "TOPGUN=F14" not in out
    assert f"TOPGUN_MAV=I feel the need..." in out
    assert f"TOPGUN_GOOSE=... the need for speed!" in out


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


def test_no_such_exec():
    """
    Test that we handle docker exec "no such exec instance" errors
    :return:
    """
    def handler(line):
        DockerJob.check_docker_exec_failed(None, line)

    comm = ProcessLineProxyThread(None, sys.stdout, linehandler=handler)
    comm.writeout(b"No such exec instance")

    assert len(comm.errors) == 1
    assert isinstance(comm.errors[0], DockerExecError)


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


def test_additional_volumes(linux_docker, capsys, envs):
    """
    Test GLE_DOCKER_VOLUMES
    :param linux_docker:
    :param capsys:
    :param envs:
    :return:
    """
    tmpdir1 = tempfile.mkdtemp()
    tmpdir2 = tempfile.mkdtemp()
    try:
        os.environ["GLE_DOCKER_VOLUMES"] = ",".join([
            f"{tmpdir1}:/volumes/dir1",
            f"{tmpdir2}:/volumes/dir2:ro"
        ])

        rnd1 = str(uuid.uuid4())
        rnd2 = str(uuid.uuid4())

        file1 = os.path.join(tmpdir1, "uuid1.txt")
        with open(file1, "w") as f1:
            f1.write(rnd1)

        file2 = os.path.join(tmpdir2, "uuid2.txt")
        with open(file2, "w") as f2:
            f2.write(rnd2)

        run(["-c", os.path.join(TEST_DIR, "test-volumes.yaml"), "vol"])

        out, err = capsys.readouterr()
        assert rnd1 in out
        assert rnd2 in out

        # check the new file was created
        newfile = os.path.join(tmpdir1, "hello.txt")
        assert os.path.exists(newfile)

        # check that the ro folder has no new files
        rofiles = os.listdir(tmpdir2)
        assert rofiles == ["uuid2.txt"], "expected only one file"

    finally:
        shutil.rmtree(tmpdir1)
        shutil.rmtree(tmpdir2)
