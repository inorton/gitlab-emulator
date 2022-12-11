"""Test that listing jobs omitted by rules are shown in the stderr/log"""
import os
from pathlib import Path
from _pytest.capture import CaptureFixture
from _pytest.logging import LogCaptureFixture
from ...runner import run

HERE = os.path.dirname(__file__)

def test_list_jobs(repo_root: str, caplog: LogCaptureFixture):
    os.chdir(Path(HERE) / "basic_job_rules")
    caplog.clear()
    run(["-l", "--debug-rules"])
    messages = caplog.messages

    assert "D: job=job: checking rule: {'when': 'on_success'}" in messages
    assert "D: job=job: rule matched" in messages
    assert "D: only_red skipped by rules: matched {'when': 'never'}" in messages
