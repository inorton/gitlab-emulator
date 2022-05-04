import os
import pytest
import subprocess
import platform
import sys

from ..userconfig import reset_user_config

TESTS_DIR = os.path.abspath(os.path.dirname(__file__))
EMULATOR_DIR = os.path.dirname(os.path.dirname(TESTS_DIR))


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
    check_docker("linux")


@pytest.fixture(scope="session")
def windows_docker():
    check_docker("windows")


def check_docker(osname):
    try:
        output = subprocess.check_output(["docker", "info", "-f", "{{.OSType}}"])
        text = output.decode().strip()
        if text != osname:
            pytest.skip("docker cannot run a {} image".format(osname))
    except Exception as err:
        pytest.skip("could not run docker info " + str(err))


@pytest.fixture(autouse=True)
def envs():
    envs = dict(os.environ)
    # strip out CI_ env vars
    for name in envs:
        if name.startswith("CI_"):
            del os.environ[name]
    yield
    for item in envs:
        os.environ[item] = envs[item]
    for item in list(os.environ.keys()):
        if item not in envs:
            del os.environ[item]


@pytest.fixture(scope="function", autouse=True)
def cwd():
    here = os.getcwd()
    yield
    os.chdir(here)


@pytest.fixture(scope="function", autouse=True)
def replace_stdout():
    if not hasattr(sys.stdout, "reconfigure"):
        pytest.skip("python 3.7 or later required for sys.stdout.reconfigure()")

    default_encoding = sys.stdout.encoding
    yield
    sys.stdout.reconfigure(encoding=default_encoding)


@pytest.fixture(scope="function", autouse=True)
def gle_reset_user_config():
    reset_user_config()
