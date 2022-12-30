import pytest
from ..runner import run

CI_FILE = "test_null_scripts.yml"


def test_null_body(in_tests, capfd):
    run(["-c", CI_FILE, "job1"])
    stdout, _ = capfd.readouterr()
    lines = stdout.splitlines()
    assert "in_script" in lines

    run(["-c", CI_FILE, "job2"])
    stdout, _ = capfd.readouterr()
    lines = stdout.splitlines()
    assert "in_before_script" in lines
