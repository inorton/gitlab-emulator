"""
Test using local docker
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import uuid
import os

from pytest_mock import MockerFixture

from ..helpers import ProcessLineProxyThread
from ..runner import run
from ..errors import DockerExecError
from ..docker import DockerJob

TOPDIR = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
TEST_DIR = os.path.join(TOPDIR, "emulator", "gitlabemu", "tests")


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


@pytest.mark.usefixtures("linux_only")
def test_job_workspace_longpath():
    job = DockerJob()
    job.workspace = "/foo/bar/baz"

    assert job.inside_workspace == "/foo/bar/baz"

    # check large paths get shortened
    job.workspace = "/foo/" + str(uuid.uuid4()) * 3 + "/bar"

    assert job.inside_workspace == "/b/bar"

def test_job_workspace_non_c_path(mocker: MockerFixture):
    job = DockerJob()
    job.workspace = "f:\\git\\work"
    mocker.patch("gitlabemu.docker.is_windows", return_value=True)
    assert job.inside_workspace == "c:\\b\\work"


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


def test_image_variables(linux_docker, capsys):
    """
    Test that we can expand variables in the job image
    :param linux_docker:
    :return:
    """
    run(["-c", os.path.join(TOPDIR, "test-ci.yml"),
         "variable_image"])

    out, err = capsys.readouterr()
    assert "CI_JOB_IMAGE=busybox:latest" in out


def test_general_variables(linux_docker, capsys):
    """
    Test that CI_PIPELINE_ID etc are expanded when used in `variables`
    :param linux_docker:
    :param capsys:
    :return:
    """
    run(["-c", os.path.join(TOPDIR, "test-ci.yml"),
         "variable_image"])

    out, err = capsys.readouterr()
    assert "$CI_PROJECT_PATH" not in out
    assert "$CI_PIPELINE_ID" not in out
    assert "MY_VARIABLE=local/gitlab-emulator/0" in out


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
    Test that we can do a simple build using docker with services defined in a job
    :param linux_docker:
    :return:
    """
    run(["-c", os.path.join(TEST_DIR, "test-services.yaml"),
         "--full", "job1"])

    out, err = capsys.readouterr()
    assert "Welcome to nginx!" in out


def test_global_services(linux_docker, capsys):
    """
    Test that we can do a simple build using docker with services defined globally
    :param linux_docker:
    :return:
    """
    run(["-c", os.path.join(TEST_DIR, "test-services.yaml"),
         "--full", "job2"])

    out, err = capsys.readouterr()
    assert "Welcome to nginx!" in out


def test_additional_volumes(linux_docker, capsys):
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


def test_git_worktree(linux_docker, top_dir):
    """
    Test support for repos that use "git worktree"
    :param linux_docker:
    :param capsys:
    :param envs:
    :return:
    """
    workdir = os.path.dirname(__file__)
    tmpdir1 = tempfile.mkdtemp(dir=workdir)
    tmpdir2 = tempfile.mkdtemp(dir=workdir)
    try:
        # clone ourself
        subprocess.check_output(["git", "clone",
                                 top_dir,
                                 tmpdir1], cwd=workdir)
        # make a worktree
        subprocess.check_output(["git", "worktree", "add", tmpdir2], cwd=tmpdir1)

        # run the check-alpine job
        run(["-c", os.path.join(tmpdir1, ".gitlab-ci.yml"), "git-alpine"])
    finally:
        shutil.rmtree(tmpdir1)
        shutil.rmtree(tmpdir2)
        subprocess.call(["git", "worktree", "prune"], cwd=os.path.dirname(__file__))


@pytest.mark.usefixtures("in_tests")
@pytest.mark.usefixtures("windows_docker")
def test_windows_docker():
    """Test we can launch a windows container job"""
    # emulator/gitlabemu/tests/test-powershell-fail.yml
    run(["-c", "test-powershell-fail.yml", "windows-powershell-ok", "--powershell"])
    run(["-c", "test-powershell-fail.yml", "windows-cmd-ok", "--cmd"])

    with pytest.raises(SystemExit):
        run(["-c", "test-powershell-fail.yml", "windows-powershell-fail", "--powershell"])
    with pytest.raises(SystemExit):
        run(["-c", "test-powershell-fail.yml", "windows-cmd-fail", "--cmd"])


@pytest.mark.usefixtures("has_docker")
@pytest.mark.usefixtures("posix_only")
def test_docker_user(top_dir, capfd):
    os.chdir(top_dir)
    uid = os.getuid()
    run(["-c", "test-ci.yml", "-u", "alpine-test"])
    stdout, stderr = capfd.readouterr()
    assert f"uid={uid}" in stdout

@pytest.mark.usefixtures("has_docker")
@pytest.mark.usefixtures("posix_only")
def test_docker_fail_shell(top_dir, capfd):
    os.chdir(top_dir)
    magic = str(uuid.uuid4())
    with pytest.raises(SystemExit):
        run(["-c", "test-ci.yml", "-u", "alpine-fail", "-e", f"echo {magic}"])
    stdout, stderr = capfd.readouterr()
    assert f"{magic}" in stdout


@pytest.mark.usefixtures("has_docker")
@pytest.mark.usefixtures("posix_only")
def test_docker_runner_exec(top_dir, capfd, temp_folder: Path):
    """Test running gitlab-runner exec"""
    os.chdir(top_dir)
    fake_gitlab_runner = temp_folder / "gitlab-runner"
    with open(fake_gitlab_runner, "w") as fd:
        print("#!/bin/sh", file=fd)
        print("echo running: \"$@\"", file=fd)
    os.chmod(str(fake_gitlab_runner), 0o755)
    os.environ["PATH"] = str(temp_folder.absolute()) + os.pathsep + os.environ["PATH"]

    run(["-c", "test-ci.yml", "--exec", "alpine-test"])
    stdout, stderr = capfd.readouterr()
    assert "running: exec docker --cicd-config-file" in stdout
