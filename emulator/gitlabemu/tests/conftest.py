import os
import random
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional, List

import pytest
import subprocess
import platform
import sys


TESTS_DIR = os.path.abspath(os.path.dirname(__file__))
EMULATOR_DIR = os.path.dirname(os.path.dirname(TESTS_DIR))


@pytest.fixture(scope="session")
def repo_root() -> str:
    return os.path.dirname(EMULATOR_DIR)


@pytest.fixture(scope="session")
def top_dir() -> str:
    return os.path.dirname(EMULATOR_DIR)


@pytest.fixture(scope="function")
def in_tests() -> str:
    initdir = os.getcwd()
    os.chdir(TESTS_DIR)
    yield os.getcwd()
    os.chdir(initdir)

@pytest.fixture(scope="function")
def custom_config():
    before = dict(os.environ)
    try:
        os.environ["GLE_CONFIG"] = "/tmp/gle-tests/test-gle-config.yml"
        if os.path.exists(os.environ["GLE_CONFIG"]):
            os.unlink(os.environ["GLE_CONFIG"])
        yield os.environ["GLE_CONFIG"]
    finally:
        os.environ.clear()
        os.environ.update(before)


@pytest.fixture(scope="session")
def linux_only() -> None:
    if platform.system() != "Linux":
        pytest.skip("not a Linux system")


@pytest.fixture(scope="session")
def windows_only() -> None:
    if platform.system() != "Windows":
        pytest.skip("not a Windows system")


@pytest.fixture(scope="session")
def posix_only() -> None:
    if platform.system() == "Windows":
        pytest.skip("not a POSIX platform")
    try:
        import posix
        assert posix.uname()
    except ImportError:
        pytest.skip("System does not have the posix module")


@pytest.fixture(scope="session")
def has_docker() -> None:
    try:
        subprocess.check_output(["docker", "info"])
    except Exception as err:
        pytest.skip("docker not available on this machine : " + str(err))


@pytest.fixture(scope="session")
def linux_docker() -> None:
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
    temp = tempfile.mkdtemp()
    envs = dict(os.environ)
    # strip out CI_ env vars
    for name in envs:
        for exclude in ["CI_", "GLE_"]:
            if name.startswith(exclude):
                del os.environ[name]
    envs["GLE_CONFIG"] = os.path.join(temp, "test-config.yaml")
    yield
    if os.path.exists(temp):
        shutil.rmtree(temp)
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


class MockPipelineJob:
    def __init__(self, pipeline, name, status):
        self.id = random.randint(1, 7873897437)
        self.pipeline = pipeline
        self.name = name
        self.status = status
        self.artifacts: List[dict] = []

class MockPipelineJobs:
    def __init__(self, pipeline):
        self.pipeline = pipeline

    def list(self, **kwargs):
        return self.pipeline.api_jobs

class MockPipeline:
    def __init__(self):
        self.id = random.randint(1, 81924)
        self.ref: Optional[str] = None
        self.status: Optional[str] = None
        self.api_jobs = []

    @property
    def jobs(self, **kwargs):
        return MockPipelineJobs(self)

    def mock_add_job(self, name, status, artifacts):
        job = MockPipelineJob(self, name, status)
        job.artifacts = artifacts
        self.api_jobs.append(job)
        return job

class MockProjectPipelines:
    def __init__(self, project):
        self._project = project

    @property
    def list(self, **kwargs):
        return self._project.api_pipelines

    def get(self, pipeline_id):
        for pipeline in self.list:
            if pipeline.id == pipeline_id:
                return pipeline
        return None


class MockAPIProject:
    def __init__(self):
        self.api_pipelines = []
        self.id = random.randint(1, 344234)

    @property
    def pipelines(self):
        return MockProjectPipelines(self)

    def mock_add_pipeline(self):
        p = MockPipeline()
        self.api_pipelines.append(p)
        return p

class MockAPIClient:

    @property
    def ssl_verify(self):
        return True
    @property
    def api_url(self):
        return "https://nowhere/gitlab"


@pytest.fixture()
def mock_client_project_remote():
    client = MockAPIClient()
    project = MockAPIProject()
    remote = "moose"
    return client, project, remote


@pytest.fixture(scope="function")
def temp_folder() -> Path:
    folder = tempfile.mkdtemp()
    yield Path(folder)
    shutil.rmtree(folder)


@pytest.fixture(scope="function")
def in_topdir(repo_root: str) -> None:
    os.chdir(repo_root)