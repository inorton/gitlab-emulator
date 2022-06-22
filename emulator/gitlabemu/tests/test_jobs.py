"""Tests for jobs.py"""
import time
import subprocess
import uuid
from pathlib import Path

import pytest

from ..jobs import NoSuchJob, Job, make_script


def test_nosuchjob():
    err = NoSuchJob("bob")
    assert str(err) == "NoSuchJob bob"


def test_job_basic():
    job = Job()
    job.name = "fred"

    assert str(job) == "job fred"

    job.started_time = time.time() - 61
    assert job.duration() > 60

    job.started_time = time.time()
    job.ended_time = job.started_time + 300
    assert job.duration() == 300


def test_abort(caplog: pytest.CaptureFixture):
    job = Job()
    job.name = "stopper"

    proc = subprocess.Popen(["/bin/sh", "-c", "sleep 600"], shell=False)
    job.build_process = proc
    assert proc.returncode is None
    job.abort()
    proc.poll()
    assert proc.returncode is not None

    assert "aborting job stopper" in caplog.messages
    assert "killing child build process.." in caplog.messages


@pytest.mark.usefixtures("posix_only")
def test_after_script(tmp_path: Path, capfd: pytest.CaptureFixture, caplog):
    """Tests that the after script still runs even if a job fails"""
    workspace = tmp_path / "work"
    workspace.mkdir()
    job = Job()
    job.name = "sidney"
    job.workspace = str(workspace)
    job.timeout_seconds = 10
    magic = str(uuid.uuid4())
    never = str(uuid.uuid4())
    job.script = [
        "exit 1",
        f"echo {never}"
    ]
    job.after_script = [
        f"echo {magic}"
    ]
    with pytest.raises(SystemExit) as err:
        job.run()
    assert err.value.code != 0

    assert job.ended_time
    assert job.started_time
    assert job.duration() < 10
    stdout, stderr = capfd.readouterr()
    assert magic in stdout
    assert never not in stdout
    assert "job sidney timeout set to 0 mins" in caplog.messages
    assert "running shell job sidney" in caplog.messages
    assert "Shell job sidney failed" in caplog.messages


@pytest.mark.usefixtures("posix_only")
def test_script_generation_unix():
    text = make_script(
        [
            "ls -l",
        ], powershell=False)
    assert "set -e\n" in text

    multi_line_script = make_script(
        [
            """
            uname -a
            df -h
            """,
            "ls -l",
        ]
    )

    assert "\n\n" in multi_line_script
    assert "uname -a\n" in multi_line_script
    assert "df -h\n" in multi_line_script

