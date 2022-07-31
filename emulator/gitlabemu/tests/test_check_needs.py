import pytest
import os

from pytest import CaptureFixture

from .. import runner


def test_run_needs_stages(in_tests, capsys: CaptureFixture):
    runner.run(["--config", "needs-stages.yml", "--full", "finish"])
    stdout, stderr = capsys.readouterr()
    assert "the-start" in stdout
    assert "the-middle" in stdout
    assert "the-end" in stdout
    assert "Build complete!" in stdout


@pytest.mark.usefixtures("posix_only")
def test_run_needs_no_stages(in_tests, capsys: CaptureFixture):
    # job creates a "stageless-start" folder to ensure start1 only gets
    # run once,
    if os.path.exists("stageless-start"):
        os.rmdir("stageless-start")
    try:
        cfgfile = os.path.join(in_tests, "settings", "gitlab-defaults.yml")
        runner.run(["--settings", cfgfile, "--config", "needs.yml", "--full", "finish"])
        stdout, stderr = capsys.readouterr()
    finally:
        if os.path.exists("stageless-start"):
            os.rmdir("stageless-start")

    assert "stageless-start-1" in stdout
    assert "stageless-start-2" in stdout
    assert "stageless-middle" in stdout
    assert "stageless-finish" in stdout
    assert "Build complete!" in stdout


def test_illegal_needs_early(in_tests, capsys: CaptureFixture):
    cfgfile = os.path.join(in_tests, "settings", "gitlab-14.1.yml")
    with pytest.raises(SystemExit):
        runner.run([
            "--settings", cfgfile,
            "--list",
            "--config", os.path.join("invalid", "14.1", "bad-needs-earlier-stage.yaml")])

    _, stderr = capsys.readouterr()

    assert "job job1 needs job2 that is not in an earlier stage" in stderr


def test_illegal_needs_same(in_tests, capsys: CaptureFixture):
    cfgfile = os.path.join(in_tests, "settings", "gitlab-14.1.yml")
    with pytest.raises(SystemExit):
        runner.run([
            "--settings", cfgfile,
            "--list",
            "--config", os.path.join("invalid", "14.1", "bad-needs-same-stage.yaml")])

    _, stderr = capsys.readouterr()

    assert "job job2 needs job1 that is not in an earlier stage" in stderr
