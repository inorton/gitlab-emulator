import sys
import os
import pytest
import subprocess
HERE = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, HERE)


@pytest.fixture(scope="function")
def tests_dir():
    os.chdir(os.path.dirname(__file__))
    return os.getcwd()


@pytest.fixture(scope="session")
def has_docker():
    try:
        subprocess.check_output(["docker", "info"])
    except Exception as err:
        pytest.skip("docker not available on this machine : " + str(err))
