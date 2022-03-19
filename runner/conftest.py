import os
import platform
import uuid
import pytest

from GitlabPyRunner.runner import Runner

GITLAB = "https://gitlab.com"


def clean_envs():
    """Strip out gitlab env vars to keep tests clean"""
    for name in os.environ.keys():
        if name.startswith("CI_"):
            del os.environ[name]


clean_envs()


@pytest.fixture()
def random_runner():
    instance = register_runner()
    yield instance
    instance.unregister()
    assert not instance.token


@pytest.fixture()
def playground_runner():

    tags = ["python-runner-new"]
    if platform.system() == "Windows":
        tags.append("python-runner-windows")
    if platform.system() == "Linux":
        tags.append("python-runner-linux")
    instance = register_runner(tags=tags)
    yield instance
    instance.unregister()
    assert not instance.token


def register_runner(tags=[]):
    token = os.getenv("TEST_REGISTRATION_TOKEN", None)
    if not token:
        pytest.skip("TEST_REGISTRATION_TOKEN is not set")
    instance = Runner(GITLAB, None)
    if not tags:
        tags = [str(uuid.uuid4())]
    instance.register("test runner", token, tags=tags)
    assert instance.token
    return instance
