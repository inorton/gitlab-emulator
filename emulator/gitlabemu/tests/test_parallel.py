import os.path

import pytest
from ..runner import run

HERE = os.path.dirname(__file__)
PARALLEL_CONFIG = os.path.join(HERE, "test_parallel.yml")

@pytest.mark.usefixtures("linux_docker")
def test_docker_parallel(top_dir, capsys):
    run(["-c", PARALLEL_CONFIG, "jobname"])

    stdout, stderr = capsys.readouterr()

    assert "CI_JOB_NAME=jobname 1/1\n" in stdout
    assert "CI_NODE_TOTAL=1\n" in stdout
    assert "CI_NODE_INDEX=1\n" in stdout

@pytest.mark.usefixtures("linux_docker")
def test_docker_parallel_m_of_n(top_dir, capsys):
    run(["-c", PARALLEL_CONFIG, "jobname", "--parallel", "2/4"])

    stdout, stderr = capsys.readouterr()

    assert "CI_JOB_NAME=jobname 2/4\n" in stdout
    assert "CI_NODE_TOTAL=4\n" in stdout
    assert "CI_NODE_INDEX=2\n" in stdout


def test_docker_parallel_m_of_n_denied(top_dir, capsys):
    with pytest.raises(SystemExit) as err:
        run(["-c", PARALLEL_CONFIG, "normaljob", "--parallel", "2/4"])
    assert err.value.code == 1
