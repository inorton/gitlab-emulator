"""
Test that the timeout keyword works
"""
import pytest
from gitlabemu import runner, helpers


def test_timeout_set_but_ample(caplog, posix_only, tests_dir):
    runner.run(["--config", "test-timeout.yaml", "run-ok"])
    assert "job run-ok timeout set to 14 mins" in caplog.messages


def test_timeout_set_job_slow(caplog, posix_only, tests_dir):
    with pytest.raises(SystemExit):
        runner.run(["--config", "test-timeout.yaml", "run-slow"])

    assert "job run-slow timeout set to 1 mins" in caplog.messages
    assert "Job exceeded timeout after 60 sec" in caplog.messages
    assert "Shell job run-slow failed" in caplog.messages


def test_timeout_parser():
    assert helpers.parse_timeout("10m") == 600.0
    assert helpers.parse_timeout("2.4m") == 144.0
    assert helpers.parse_timeout("45") == 2700
    assert helpers.parse_timeout("1h 15m") == 4500

    assert helpers.parse_timeout("2 hours") == 60 * 60 * 2
    assert helpers.parse_timeout("10 minutes") == 10 * 60
    assert helpers.parse_timeout("2 hours 2 minutes") == 120 + (60 * 60 * 2)
