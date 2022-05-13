"""Tests running local shells"""
import pytest
import os
from ..runner import run


@pytest.mark.usefixtures("windows_only")
def test_local_shell_windows(top_dir, capfd):
    """Test a basic shell script job works and fails correctly"""
    folder = os.path.join(top_dir, "emulator", "gitlabemu", "tests")
    os.chdir(folder)
    # should print to stderr without failing the build
    run(["-c", "test-powershell-fail.yml", "windows-powershell-ok", "--powershell", "--ignore-docker"])
    stdout, _ = capfd.readouterr()
    assert "this goes to stderr" in stdout
    assert "this is powershell" in stdout
