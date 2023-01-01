import os

from .. import configloader
from ..docker import DockerJob



def test_inherit(in_tests: str):
    """Test the inherit keyword"""
    loader = configloader.Loader()
    loader.load(os.path.join(in_tests, "test-inherit.yaml"))

    job1: DockerJob = loader.load_job("job1")
    job2: DockerJob = loader.load_job("job2")
    job3: DockerJob = loader.load_job("job3")
    job4: DockerJob = loader.load_job("job4")
    job5: DockerJob = loader.load_job("job5")

    assert job1.docker_image == "ruby:3.0"
    assert job1.before_script == ["df -h"]
    assert job1.variables["COLOR"] == "red"
    assert job2.docker_image == "ruby:3.0"
    assert job2.before_script == []
    assert job2.variables["COLOR"] == "red"

    assert job3.docker_image == job2.docker_image
    assert job3.before_script == job2.before_script
    assert job3.variables["COLOR"] == "red"
    assert job3.variables["SIZE"] == "big"

    assert "COLOR" in job4.variables
    assert "SIZE" not in job4.variables
    assert job4.before_script == ["df -h"]
    assert job4.script == ['echo COLOR="$COLOR"', 'echo SIZE="$SIZE"']

    assert "COLOR" not in job5.variables
    assert "SIZE" not in job5.variables
    assert job5.before_script == ["df -h"]
    assert job5.script == ["echo job5 script"]
