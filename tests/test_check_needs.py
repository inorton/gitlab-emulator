import pytest
import os

from gitlabemu import runner, configloader


def test_run_needs(tests_dir):
    runner.run(["--config", "test-needs.yaml", "--full", "finish"])


def test_illegal_needs_early(tests_dir, capsys):
    with pytest.raises(SystemExit):
        runner.run([
            "--list",
            "--config", os.path.join("invalid", "bad-needs-earlier-stage.yaml")])

    stderr, stdout = capsys.readouterr()

    assert "job job1 needs job2 that is not in an earlier stage" in stderr


def test_illegal_needs_same(tests_dir, capsys):
    with pytest.raises(SystemExit):
        runner.run([
            "--list",
            "--config", os.path.join("invalid", "bad-needs-same-stage.yaml")])

    stderr, stdout = capsys.readouterr()

    assert "job job2 needs job1 that is not in an earlier stage" in stderr
