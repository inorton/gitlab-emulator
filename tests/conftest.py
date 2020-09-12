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


@pytest.fixture(scope="session")
def linux_docker():
    try:
        output = subprocess.check_output(["docker", "info", "-f", "{{.OSType}}"])
        text = output.decode().strip()
        if text != "linux":
            pytest.skip("docker cannot run a linux image")
    except Exception as err:
        pytest.skip("could not run docker info " + str(err))
