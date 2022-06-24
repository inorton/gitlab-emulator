"""Tests for --pipeline option"""
import os
import subprocess

import pytest
import yaml
from requests_mock import Mocker

from ..runner import run
from ..configloader import Loader
from ..generator import generate_pipeline_yaml, create_pipeline_branch, wait_for_project_commit_pipeline
from ..helpers import git_commit_sha
from .mocked_gitlab import MockServer, MOCK_HOST


HERE = os.path.abspath(os.path.dirname(__file__))
MOCKED_PROJECT_DIR = os.path.join(HERE, "mocked_project")


def test_mocked_list(top_dir: str,
                     mocker,
                     requests_mock: Mocker,
                     capfd: pytest.CaptureFixture):
    pipeline, project = mock_project_pipeline(requests_mock)
    mock_git_origin(mocker, project)
    run(["-C", top_dir, "--pipeline", "--list"])

    stdout, stderr = capfd.readouterr()
    assert project.name in stderr
    assert project.server.url in stderr

    assert str(pipeline.id) in stdout
    assert pipeline.status in stdout
    assert pipeline.sha in stdout
    assert pipeline.ref in stdout


def mock_project_pipeline(requests_mock):
    os.environ["GITLAB_PRIVATE_TOKEN"] = "123"
    project = MockServer(requests_mock, MOCK_HOST).setup(jobnames=["job1", "job2"])
    pipeline = project.pipelines[0]
    return pipeline, project


def mock_git_origin(mocker, project):
    mocker.patch("gitlabemu.gitlab_client_api.get_git_remote_urls",
                 return_value={
                     "origin": project.http_url_to_repo
                 })


def test_mocked_generate(capfd: pytest.CaptureFixture):
    os.chdir(MOCKED_PROJECT_DIR)
    loader = Loader()
    loader.load(".gitlab-ci.yml")
    generated = generate_pipeline_yaml(loader, "job2", "job3")

    assert "job3" in generated
    assert "job2" in generated
    assert "job1" in generated
    assert "stages" in generated
    assert "job4" not in generated


@pytest.mark.usefixtures("linux_only")
def test_mocked_branch_creation(tmp_path, mocker):
    pushed = mocker.patch("gitlabemu.generator.git_push_force_upstream", autospec=True)

    repo = tmp_path / "repo"
    repo.mkdir()
    repo = str(repo)
    # make this a git repo
    subprocess.check_call(["git", "init"], cwd=repo)
    subprocess.check_call(["git", "remote", "add", "my-remote", "http://git.server.none/repo"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "user"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "user@host.com"], cwd=repo)
    subprocess.check_call(["git", "checkout", "-b", "my-branch"], cwd=repo)
    with open(os.path.join(repo, ".gitlab-ci.yml"), "w") as fd:
        yaml.safe_dump({
            "job1": {
                "image": "alpine:latest",
                "script": ["ls -l"]
            },
            "job2": {
                "needs": ["job1"],
                "script": ["ls -l"]
            }
        }, fd, default_flow_style=False, indent=2)
    subprocess.check_call(["git", "add", ".gitlab-ci.yml"], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "initial commit", ".gitlab-ci.yml"], cwd=repo)
    initial_commit = git_commit_sha(repo)
    commit = create_pipeline_branch(repo, "my-origin", "my-new-branch", "my-new-commit",
                                    {
                                        "hello.txt": "hello world"
                                    })
    restored_commit = git_commit_sha(repo)

    assert pushed.called
    assert commit
    assert restored_commit == initial_commit
    assert commit != restored_commit