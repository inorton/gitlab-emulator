import pytest
from ..runner import run

CI_FILE = "test_before_script_after.yml"


@pytest.mark.usefixtures("posix_only")
def test_just_before(in_tests, capfd):
    run(["-c", CI_FILE, "job", "-b"])
    stdout, _ = capfd.readouterr()
    lines = stdout.splitlines()
    assert "SCRIPT_STAGE=before" in lines
    assert "SCRIPT_STAGE=script" not in lines
    assert "SCRIPT_STAGE=after" not in lines


@pytest.mark.usefixtures("posix_only")
@pytest.mark.usefixtures("has_docker")
def test_just_before_docker(in_tests, capfd):
    run(["-c", CI_FILE, "docker_job", "-b"])
    stdout, _ = capfd.readouterr()
    lines = stdout.splitlines()
    assert "SCRIPT_STAGE=before" in lines
    assert "SCRIPT_STAGE=script" not in lines
    assert "SCRIPT_STAGE=after" not in lines


@pytest.mark.usefixtures("posix_only")
def test_all_scripts(in_tests, capfd):
    run(["-c", CI_FILE, "job"])
    stdout, _ = capfd.readouterr()
    lines = stdout.splitlines()
    assert "SCRIPT_STAGE=before" in lines
    assert "SCRIPT_STAGE=script" in lines
    assert "SCRIPT_STAGE=after" in lines

