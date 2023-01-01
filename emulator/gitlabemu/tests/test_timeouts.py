"""
Test that the timeout keyword works
"""
import time
import pytest
from pytest_mock import MockerFixture

from .. import runner, helpers, logmsg


def test_timeout_set_but_ample(caplog, posix_only, in_tests):
    runner.run(["--config", "test-timeout.yaml", "run-ok"])
    assert "job run-ok timeout set to 14 mins" in caplog.messages


@pytest.mark.usefixtures("linux_only")
def test_timeout_set_job_slow(caplog, in_tests, mocker: MockerFixture):
    now = time.monotonic()
    patched_time = None
    def mocked_time() -> float:
        rv =  now + patched_time.call_count * 25
        logmsg.info(f"time.monotonic() -> {rv}")
        return rv

    with pytest.raises(SystemExit):
        logmsg.info("patching time.monotonic..")
        patched_time = mocker.patch("time.monotonic", side_effect=mocked_time)
        runner.run(["--config", "test-timeout.yaml", "run-slow"])

    assert "job run-slow timeout set to 1 mins" in caplog.messages
    assert "Job exceeded 60 sec timeout" in caplog.messages
    assert "kill container run-slow" in caplog.messages
    assert "E!: Docker job run-slow failed" in caplog.messages


def test_timeout_parser():
    assert helpers.parse_timeout("10m") == 600.0
    assert helpers.parse_timeout("2.4m") == 144.0
    assert helpers.parse_timeout("45") == 2700
    assert helpers.parse_timeout("1h 15m") == 4500

    assert helpers.parse_timeout("2 hours") == 60 * 60 * 2
    assert helpers.parse_timeout("10 minutes") == 10 * 60
    assert helpers.parse_timeout("2 hours 2 minutes") == 120 + (60 * 60 * 2)
