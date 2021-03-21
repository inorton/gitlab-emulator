import os
import platform
import uuid
import pytest

from GitlabPyRunner.runner import Runner

GITLAB = "https://gitlab.com"


@pytest.yield_fixture()
def random_runner():
    instance = register_runner()
    yield instance
    instance.unregister()
    assert not instance.token


@pytest.yield_fixture()
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
