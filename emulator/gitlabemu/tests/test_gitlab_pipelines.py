"""Tests for --pipeline option"""
import os

import pytest
from requests_mock import Mocker

from ..runner import run
from .mocked_gitlab import MockServer, MOCK_HOST


def test_mocked_list(top_dir: str,
                     mocker,
                     requests_mock: Mocker,
                     capfd: pytest.CaptureFixture):
    os.environ["GITLAB_PRIVATE_TOKEN"] = "123"
    project = MockServer(requests_mock, MOCK_HOST).setup(jobnames=["job1", "job2"])
    pipeline = project.pipelines[0]
    mocker.patch("gitlabemu.gitlab_client_api.get_git_remote_urls", return_value=[
        project.http_url_to_repo
    ])
    run(["-C", top_dir, "--pipeline", "--list"])

    stdout, stderr = capfd.readouterr()
    assert project.name in stderr
    assert project.server.url in stderr

    assert str(pipeline.id) in stdout
    assert pipeline.status in stdout
    assert pipeline.sha in stdout
    assert pipeline.ref in stdout
