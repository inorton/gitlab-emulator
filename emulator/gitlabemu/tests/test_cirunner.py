import os
import random
import sys
import uuid
from io import StringIO
from pathlib import Path
import pytest
import requests
from requests_mock import Mocker
from .mocked_gitlab import MockServer
from ..cirunner.runner import RunnerConfig, TraceUploader, JobRunner, run


def test_runner_config(in_topdir):
    cfg = RunnerConfig()
    envs = cfg.get_envs()
    assert "HTTP_PROXY" not in envs
    assert "HTTPS_PROXY" not in envs

    assert cfg.ca_cert is None
    assert cfg.token == ""

    cfg.load(Path("example-runner-proxy.yml"))

    envs = cfg.get_envs()
    assert "HTTP_PROXY" in envs
    assert "HTTPS_PROXY" in envs

    assert cfg.token == "runner-token-secret-string"


def test_runner_bad_config(in_topdir, caplog, capfd):
    with pytest.raises(requests.HTTPError) as err:
        run(["--builds", os.getcwd(), "--config", "example-runner.yml"])

    assert err.value.response.status_code == 403


class MockTracer(TraceUploader):
    def __init__(self):
        super().__init__("url", "token", "123", None)
        self.sent = StringIO()

    def send(self, data):
        self.sent.write(data)
        self.offset += len(data)


def test_jobrunner(mocker, tmp_path):
    glr = JobRunner("https://gitlab-server", "runner-token")
    glr.tracer = MockTracer()
    glr.workdir = tmp_path
    check_output = mocker.patch("subprocess.check_output", return_value="git command output")
    glr.git_clone("https://gitrepo", "project", "abcd1234")
    assert check_output.called
    traced = glr.tracer.sent.getvalue()
    glr.tracer.flush()
    assert "clone https://gitrepo into " in traced
    assert "checkout abcd1234" in traced
    assert "git command output" in traced


def test_mock_request_nojobs(tmp_path, caplog):
    with Mocker() as m:
        server = MockServer(m, "gitlab-server")
        # no content
        m.post(f"{server.server.url}/api/v4/jobs/request", status_code=204)
        glr = JobRunner(server.server.url, "runner-token")
        glr.tracer = MockTracer()
        glr.workdir = tmp_path
        glr.poll()
    messages = caplog.messages
    assert "no job" in messages


def test_mock_request_one_job(mocker, tmp_path, caplog):
    check_output = mocker.patch("subprocess.check_output", return_value="git command output")
    jobid = random.randint(99, 876542)
    token = str(uuid.uuid4())
    with Mocker() as m:
        server = MockServer(m, "gitlab-server")
        # accept a trace message
        m.patch(f"{server.server.url}/api/v4/jobs/{jobid}/trace", status_code=200)

        # upload artifact
        m.post(f"{server.server.url}/api/v4/jobs/{jobid}/artifacts", status_code=200)

        # job done
        m.put(f"{server.server.url}/api/v4/jobs/{jobid}", status_code=200)

        # a job
        m.post(f"{server.server.url}/api/v4/jobs/request", status_code=201, json={
            "id": jobid,
            "token": token,
            "job_info": {
                "name": "myjob",
                "project_name": "project",
            },
            "git_info": {
                "repo_url": f"{server.server.url}/group/project.git",
                "sha": "ab12" * 10
            },
            "artifacts": [
                {
                    "artifact_type": "archive",
                    "artifact_format": "zip",
                    "paths": [
                        "pwd.txt"
                    ]
                }
            ],
            "variables": [
                {
                    "key": "MOOSE",
                    "value": "Bullwinkle",
                    "masked": False,
                },
                {
                    "key": "SECRET_VAR",
                    "value": "potato",
                    "masked": True,
                }
            ],
            "steps": [
                {
                    "name": "script",
                    "timeout": 64,
                    "script": [
                        f"{sys.executable} -c 'import os; print(os.getcwd())'",
                        f"{sys.executable} -c 'import os; print(os.getcwd())' > pwd.txt",
                    ]
                }
            ]
        })
        glr = JobRunner(server.server.url, "runner-token")
        glr.tracer = MockTracer()
        glr.workdir = tmp_path
        (glr.workdir / "project").mkdir()
        glr.poll()
    messages = caplog.messages
    assert check_output.called
    assert f"got a job id={jobid}" in messages
    assert "running shell job myjob" in messages
    assert f"job {jobid} done" in messages

