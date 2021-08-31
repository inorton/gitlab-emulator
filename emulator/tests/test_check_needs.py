import pytest
import os

from gitlabemu import runner


def test_run_needs_stages(in_tests, envs):
    os.environ["GLE_CONFIG"] = os.path.join(os.getcwd(), "gle-config-v14.1.yaml")
    runner.run(["--config", "test-needs-14.1.yaml", "--full", "finish"])


def test_run_needs_no_stages(in_tests, envs):
    os.environ["GLE_CONFIG"] = os.path.join(os.getcwd(), "gle-config-v14.2.yaml")
    runner.run(["--config", "test-needs-14.2.yaml", "--full", "finish"])


def test_illegal_needs_early(in_tests, capsys, envs):
    os.environ["GLE_CONFIG"] = os.path.join(os.getcwd(), "gle-config-v14.1.yaml")
    with pytest.raises(SystemExit):
        runner.run([
            "--list",
            "--config", os.path.join("invalid", "bad-needs-earlier-stage.yaml")])

    _, stderr = capsys.readouterr()

    assert "job job1 needs job2 that is not in an earlier stage" in stderr


def test_illegal_needs_same(in_tests, capsys, envs):
    os.environ["GLE_CONFIG"] = os.path.join(os.getcwd(), "gle-config-v14.1.yaml")
    with pytest.raises(SystemExit):
        runner.run([
            "--list",
            "--config", os.path.join("invalid", "bad-needs-same-stage.yaml")])

    _, stderr = capsys.readouterr()

    assert "job job2 needs job1 that is not in an earlier stage" in stderr
