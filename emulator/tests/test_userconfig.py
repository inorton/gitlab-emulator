"""
Test that the config file system works
"""
import os
import shutil
import tempfile

from gitlabemu import runner


def test_load_userconfig(top_dir, envs):
    if "GLE_DOCKER_VOLUMES" in os.environ:
        del os.environ["GLE_DOCKER_VOLUMES"]
    os.environ["GLE_CONFIG"] = os.path.join(top_dir, "emulator", "configs", "example-emulator.yml")
    cfg = runner.load_user_config()
    assert cfg["emulator"]["variables"]["SOME_VAR_NAME"] == "hello"


def test_run_userconfig(top_dir, envs, has_docker, capfd):
    if "GLE_DOCKER_VOLUMES" in os.environ:
        del os.environ["GLE_DOCKER_VOLUMES"]
    os.environ["GLE_CONFIG"] = os.path.join(top_dir, "emulator", "configs", "example-emulator.yml")
    pipeline = os.path.join(top_dir, "emulator", "tests", "basic.yml")

    # create a temp dir that will be in our bound volume
    tempdir = tempfile.mkdtemp(dir="/tmp")
    try:
        runner.run(["-c", pipeline, "vars-job"])
        stdout, stderr = capfd.readouterr()
        assert "Reading gle config from " in stdout
        tempname = os.path.basename(tempdir)
        assert tempname in stdout
    finally:
        shutil.rmtree(tempdir)
