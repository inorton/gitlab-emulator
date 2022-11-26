"""Test the --from options"""
import os
import random
import shutil
import subprocess

import pytest
import argparse

from requests_mock.mocker import Mocker
from requests import ConnectionError

from . import mocked_gitlab
from .mocked_gitlab import MOCK_PROJECT_DIR, MOCK_HOST
from ..gitlab_client_api import parse_gitlab_from_arg
from ..runner import do_gitlab_from, run
from ..userconfig import get_user_config


@pytest.mark.usefixtures("posix_only")
def test_from_missing_download_args(capsys):
    with pytest.raises(SystemExit):
        do_gitlab_from(argparse.Namespace(FROM=None, download=True), None)

    _, stderr = capsys.readouterr()
    assert "--download requires --from PIPELINE" in stderr


@pytest.mark.usefixtures("linux_only")
def test_from_without_job_or_download(capfd):
    os.environ["GITLAB_PRIVATE_TOKEN"] = ""
    with pytest.raises(SystemExit):
        run(["--from", "nosuch.gitlab/grp/proj/1234"])
    _, stderr = capfd.readouterr()
    assert "--from PIPELINE requires JOB or --export" in stderr


@pytest.mark.usefixtures("linux_only")
def test_no_token_or_config(capfd):
    os.environ["GITLAB_PRIVATE_TOKEN"] = ""
    with pytest.raises(SystemExit):
        run(["--from", "nosuch.gitlab/grp/proj/1234", "--list"])
    _, stderr = capfd.readouterr()
    assert "Could not find a configured token for nosuch.gitlab" in stderr
    cfg = get_user_config()
    ctx = cfg.contexts[cfg.current_context]
    ctx.gitlab.add("nosuch.gitlab", "https://myserver.nosuch", "token", True)
    cfg.save()

    # should fail to connect
    with pytest.raises(ConnectionError) as err:
        run(["--from", "nosuch.gitlab/grp/proj/1234", "--list"])
    assert err.value.request.url == "https://myserver.nosuch/"
    assert err.value.request.method == "HEAD"


@pytest.fixture(scope="function", autouse=True)
def clean_mocked_project():
    os.environ["GLE_CONFIG"] = os.path.join(MOCK_PROJECT_DIR, "gle.yml")
    os.chdir(MOCK_PROJECT_DIR)
    keep = [".gitlab-ci.yml", ".gitignore"]
    savedir = os.path.join(MOCK_PROJECT_DIR, "savedir")
    if os.path.exists(savedir):
        shutil.rmtree(savedir)
    for filename in os.listdir(MOCK_PROJECT_DIR):
        if filename not in keep:
            path = os.path.join(MOCK_PROJECT_DIR, filename)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.unlink(path)


def test_mock_list_pipelines(requests_mock: Mocker, capfd: pytest.CaptureFixture):
    os.environ["GITLAB_PRIVATE_TOKEN"] = "123"
    project = mocked_gitlab.MockServer(requests_mock, MOCK_HOST).setup(jobnames=["job1", "job2"])
    pipeline = random.choice(project.pipelines)

    simple_path = f"{MOCK_HOST}/{project.path_with_namespace}/{pipeline.id}"

    run(["--list", "--completed", "--from", simple_path])
    stdout, stderr = capfd.readouterr()
    assert "job1\n" in stdout
    assert "job2\n" in stdout

    unknown_path = f"{MOCK_HOST}/{project.path_with_namespace}/1"
    requests_mock.get(f"https://{MOCK_HOST}/api/v4/projects/{project.id}/pipelines/1",
                      status_code=404)
    with pytest.raises(SystemExit):
        run(["--list", "--from", unknown_path])
    stdout, stderr = capfd.readouterr()
    assert f"Cannot find pipeline '{unknown_path}'" in stderr


@pytest.mark.usefixtures("linux_only")
def test_mock_download(requests_mock: Mocker, capfd: pytest.CaptureFixture):
    """Test downloading individual job artifacts"""
    os.environ["GITLAB_PRIVATE_TOKEN"] = "aaaaa"
    os.environ["CI_SERVER_TLS_CA_FILE"] = "/not/exist.crt"
    project = mocked_gitlab.MockServer(requests_mock, MOCK_HOST).setup(jobnames=["job1", "job2"])
    pipeline = random.choice(project.pipelines)
    simple_path = f"{MOCK_HOST}/{project.path_with_namespace}/{pipeline.id}"

    for job in pipeline.jobs:
        run(["-k", "--download", job.name, "--from", simple_path])
        _, stderr = capfd.readouterr()
        assert "TLS server validation disabled" in stderr
        assert f"Download '{job.name}' artifacts" in stderr
        assert os.path.isfile(f"artifact.{job.name}.txt")


@pytest.mark.usefixtures("linux_only")
def test_mock_from(requests_mock: Mocker, capfd: pytest.CaptureFixture):
    """Test downloading the artifacts needed by a local job"""
    os.environ["GITLAB_PRIVATE_TOKEN"] = "aaaaa"
    project = mocked_gitlab.MockServer(requests_mock, MOCK_HOST).setup(jobnames=["job1", "job2"])
    pipeline = random.choice(project.pipelines)
    simple_path = f"{MOCK_HOST}/{project.path_with_namespace}/{pipeline.id}"

    # job2 needs job1, so this should fetch job1's artifact files only
    run(["-k", "job2", "--from", simple_path])
    _, stderr = capfd.readouterr()
    assert "TLS server validation disabled" in stderr
    assert "Download artifacts required by 'job2'" in stderr
    assert os.path.isfile("artifact.job1.txt")
    assert not os.path.isfile("artifact.job2.txt")

    # test just the number for the current git repo
    subprocess.check_call(["git", "init"])
    subprocess.check_call(["git", "remote", "add", "origin", f"https://{MOCK_HOST}/{project.path_with_namespace}.git"])
    run(["-k", "job2", "--from", str(pipeline.id)])
    _, stderr = capfd.readouterr()
    assert "TLS server validation disabled" in stderr
    assert "Download artifacts required by 'job2'" in stderr
    assert os.path.isfile("artifact.job1.txt")
    assert not os.path.isfile("artifact.job2.txt")


@pytest.mark.usefixtures("linux_only")
def test_mock_export(requests_mock: Mocker, capfd: pytest.CaptureFixture):
    """Test exporting a whole pipeline including traces"""
    os.chdir(MOCK_PROJECT_DIR)
    os.environ["GITLAB_PRIVATE_TOKEN"] = "aaaaa"
    mocked = mocked_gitlab.MockServer(requests_mock, MOCK_HOST)
    project = mocked.setup(jobnames=["job1", "job2"])
    pipeline = random.choice(project.pipelines)
    simple_path = f"{MOCK_HOST}/{project.path_with_namespace}/{pipeline.id}"

    run(["--export", "savedir", "--from", simple_path])
    _, stderr = capfd.readouterr()

    assert "Fetching job job1 .. done" in stderr
    assert "Fetching job job2 .. done" in stderr
    assert "Unpack job job1 archive into savedir/job1" in stderr
    assert "Unpack job job2 archive into savedir/job2" in stderr
    export_dir = os.path.join(MOCK_PROJECT_DIR, "savedir")
    assert os.path.exists(export_dir)
    for job in pipeline.jobs:
        exported_job_dir = os.path.join(export_dir, job.name)
        assert os.path.isdir(exported_job_dir)


def test_parse_pipeline():
    result = parse_gitlab_from_arg("server.com/group1/group2/project/123456")
    assert result.server == "server.com"
    assert result.project == "group1/group2/project"
    assert result.pipeline == 123456
    assert result.gitref is None

    result = parse_gitlab_from_arg("server/group/proj=some/developer_branch")
    assert result.server == "server"
    assert result.gitref == "some/developer_branch"
    assert result.project == "group/proj"
    assert result.pipeline is None

    result = parse_gitlab_from_arg("81923")
    assert result.server is None
    assert result.gitref is None
    assert result.project is None
    assert result.pipeline == 81923

    result = parse_gitlab_from_arg("=main")
    assert result.server is None
    assert result.gitref == "main"
    assert result.project is None
    assert result.pipeline is None

    result = parse_gitlab_from_arg("moose/dog")
    assert result.server is None
    assert result.pipeline is None
    assert result.project is None
    assert result.gitref is None


def test_invalid_pipeline(capsys):
    with pytest.raises(SystemExit):
        run(["--from", "moose/group", "--list"])
    _, stderr = capsys.readouterr()
    assert "error: 'moose/group' is not a valid pipeline specification" in stderr
