"""Tests for gle --full"""
import pytest
import random
from ..runner import run, configloader

@pytest.mark.usefixtures("in_tests")
def test_loaded_jobs():
    loader = configloader.Loader()
    loader.load("jobvars.yml")
    jobs = ["one", "two", "three", "two", "one", "two", "three"]

    for name in jobs:
        job = loader.load_job(name)
        assert job.extra_variables["CI_JOB_NAME"] == name
        envs = job.get_envs()
        assert envs["CI_JOB_NAME"] == name


@pytest.mark.usefixtures("in_tests")
@pytest.mark.usefixtures("linux_docker")
def test_full_variables(capfd):
    run(["--full", "three", "-c", "jobvars.yml", "-n"])
    stdout, stderr = capfd.readouterr()
    for name in ["one", "two", "three"]:
        assert f"setenv CI_JOB_NAME={name}" in stdout
