import pytest
from ..runner import run


def test_version(capfd):
    with pytest.raises(SystemExit):
        run(["--version"])
    stdout, _ = capfd.readouterr()
    assert "1.5." in stdout


@pytest.mark.usefixtures("in_topdir")
def test_not_parallel(capfd):
    with pytest.raises(SystemExit):
        run(["--parallel", "1", "quick"])
    _, stderr = capfd.readouterr()
    assert "quick is not a parallel enabled job" in stderr


@pytest.mark.usefixtures("in_topdir")
def test_nosuch_job(capfd):
    with pytest.raises(SystemExit):
        run(["--parallel", "1", "baaaaa"])
    _, stderr = capfd.readouterr()
    assert "No such job baaaaa" in stderr


@pytest.mark.usefixtures("in_topdir")
def test_usage(capfd):
    with pytest.raises(SystemExit):
        run([])
    stdout, stderr = capfd.readouterr()
    assert "usage: " in stdout


@pytest.mark.usefixtures("in_tests")
def test_parallel_full_mutex_from(capfd):
    with pytest.raises(SystemExit):
        run(["--from", "1234", "--full", "--parallel", "1/1", "-c", "test_parallel.yml", "jobname"])
    _, stderr = capfd.readouterr()
    assert "--full and --parallel cannot be used together" in stderr
