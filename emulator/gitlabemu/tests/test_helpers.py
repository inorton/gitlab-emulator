"""Tests for helpers.py"""
import os
import sys

import docker.errors
import pytest
import subprocess
import uuid
from io import StringIO
from ..helpers import communicate, clean_leftovers, debug_enabled, make_path_slug
from random import randint


@pytest.mark.usefixtures("posix_only")
def test_communicate() -> None:
    magic = str(uuid.uuid4())
    script = f"echo '{magic}'\n".encode()
    output = StringIO()
    proc = subprocess.Popen(["/bin/sh", "-"], shell=False,
                            stdin=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            stdout=subprocess.PIPE
                            )

    communicate(proc, stdout=output, script=script)

    output.seek(0)
    content = output.read()

    assert magic in content


@pytest.mark.usefixtures("posix_only")
def test_communicate_throws() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(1)"], shell=False,
                            stderr=subprocess.STDOUT,
                            stdout=subprocess.PIPE
                            )
    with pytest.raises(subprocess.CalledProcessError):
        communicate(proc, script=None, throw=True)


@pytest.mark.usefixtures("linux_docker")
def test_clean_leftovers():
    from ..docker import DockerTool
    tool = DockerTool()
    random_id = str(randint(1, 999999))
    # create a container and network and clean them up
    container_name = "gle-docker-9999999-footest" + random_id
    network_name = "gle-network-9999999-abcd" + random_id

    tool.client.containers.run(
        image="alpine:latest",
        name=container_name,
        stdin_open=True,
        detach=True, remove=True)
    container = tool.client.containers.get(container_name)
    assert container.status

    # create a network, attach the container to it
    network = tool.client.networks.create(name=network_name)
    network.connect(container_name)

    clean_leftovers()

    # container and network should now be gone
    with pytest.raises(docker.errors.NotFound):
        tool.client.containers.get(container_name)

    with pytest.raises(docker.errors.NotFound):
        tool.client.networks.get(network_name)


def test_debug_enabled():
    for afirm in ["y", "yes", "1"]:
        os.environ["GITLAB_EMULATOR_DEBUG"] = afirm
        assert debug_enabled()

    for negat in ["0", "no", "moose", str(uuid.uuid4())]:
        os.environ["GITLAB_EMULATOR_DEBUG"] = negat
        assert not debug_enabled()


def test_make_path_slug():
    assert "Foo_Bar_123" == make_path_slug("Foo/Bar 123")
