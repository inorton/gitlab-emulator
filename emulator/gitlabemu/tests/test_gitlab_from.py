"""Test the --from options"""
import os
import random
import shutil

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


def test_no_token_or_config(capfd):
    with pytest.raises(SystemExit):
        run(["--from", "nosuch.gitlab/grp/proj/1234"])
    _, stderr = capfd.readouterr()
    assert "Could not find a configured token for nosuch.gitlab"
    cfg = get_user_config()
    ctx = cfg.contexts[cfg.current_context]
    ctx.gitlab.add("nosuch.gitlab", "https://myserver.nosuch", "token", True)
    cfg.save()

    # should fail to connect
    with pytest.raises(ConnectionError) as err:
        run(["--from", "nosuch.gitlab/grp/proj/1234"])
    assert err.value.request.url == 'https://myserver.nosuch/api/v4/projects/grp%2Fproj'


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
    assert f"Listing completed jobs in {simple_path}" in stderr
    assert "job1\n" in stdout
    assert "job2\n" in stdout

    unknown_path = f"{MOCK_HOST}/{project.path_with_namespace}/1"
    requests_mock.get(f"https://{MOCK_HOST}/api/v4/projects/{project.id}/pipelines/1",
                      status_code=404)
    with pytest.raises(SystemExit):
        run(["--list", "--from", unknown_path])
    stdout, stderr = capfd.readouterr()
    assert f"Cannot find pipeline '{unknown_path}'" in stderr



@pytest.mark.usefixtures("posix_only")
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


@pytest.mark.usefixtures("posix_only")
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


@pytest.mark.usefixtures("posix_only")
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

    assert f"Exporting job1 artifacts from {simple_path}" in stderr
    assert f"Exporting job2 artifacts from {simple_path}" in stderr
    assert "Saving log to savedir/job1/trace.log" in stderr
    assert "Saving log to savedir/job2/trace.log" in stderr
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
        run(["--from", "moose/group", "--download", "bob"])
    _, stderr = capsys.readouterr()
    assert "error: 'moose/group' is not a valid pipeline specification" in stderr
