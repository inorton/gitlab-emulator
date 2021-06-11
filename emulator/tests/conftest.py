import os
import pytest
import subprocess
import platform
import sys

TESTS_DIR = os.path.abspath(os.path.dirname(__file__))
EMULATOR_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, EMULATOR_DIR)


@pytest.fixture(scope="session")
def top_dir():
    return os.path.dirname(EMULATOR_DIR)


@pytest.fixture(scope="function")
def in_tests():
    initdir = os.getcwd()
    os.chdir(TESTS_DIR)
    yield os.getcwd()
    os.chdir(initdir)


@pytest.fixture(scope="session")
def posix_only():
    if platform.system() == "Windows":
        pytest.skip("not a POSIX platform")
    try:
        import posix
        assert posix.uname()
    except ImportError:
        pytest.skip("System does not have the posix module")


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


@pytest.fixture()
def envs():
    envs = dict(os.environ)
    yield
    for item in envs:
        os.environ[item] = envs[item]
    for item in list(os.environ.keys()):
        if item not in envs:
            del os.environ[item]
