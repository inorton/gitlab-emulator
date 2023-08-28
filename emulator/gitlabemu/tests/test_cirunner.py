import os
from pathlib import Path

import pytest
import requests

from ..cirunner.runner import RunnerConfig, run


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
