"""
Test that the timeout keyword works
"""
import pytest
from gitlabemu import runner


def test_timeout_set_but_ample(caplog, posix_only, tests_dir):
    runner.run(["--config", "test-timeout.yaml", "run-ok"])
    assert "job run-ok timeout set to 1 mins" in caplog.messages


def test_timeout_set_job_slow(caplog, posix_only, tests_dir):
    with pytest.raises(SystemExit):
        runner.run(["--config", "test-timeout.yaml", "run-slow"])

    assert "job run-slow timeout set to 1 mins" in caplog.messages
    assert "Job exceeded timeout after 60 sec" in caplog.messages
    assert "Shell job run-slow failed" in caplog.messages
