import pytest
import os

from gitlabemu import runner


def test_run_needs(in_tests):
    runner.run(["--config", "test-needs.yaml", "--full", "finish"])


def test_illegal_needs_early(in_tests, capsys):
    with pytest.raises(SystemExit):
        runner.run([
            "--list",
            "--config", os.path.join("invalid", "bad-needs-earlier-stage.yaml")])

    stderr, stdout = capsys.readouterr()

    assert "job job1 needs job2 that is not in an earlier stage" in stderr


def test_illegal_needs_same(in_tests, capsys):
    with pytest.raises(SystemExit):
        runner.run([
            "--list",
            "--config", os.path.join("invalid", "bad-needs-same-stage.yaml")])

    stderr, stdout = capsys.readouterr()

    assert "job job2 needs job1 that is not in an earlier stage" in stderr
