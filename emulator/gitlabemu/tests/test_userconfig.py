"""
Test that the config file system works
"""
import os
import platform
import shutil
import tempfile
from pathlib import Path

import pytest

from .. import runner, userconfig


def test_load_userconfig(top_dir):
    if "GLE_DOCKER_VOLUMES" in os.environ:
        del os.environ["GLE_DOCKER_VOLUMES"]
    os.environ["GLE_CONFIG"] = os.path.join(top_dir, "emulator", "configs", "example-emulator.yml")
    ctx = userconfig.get_user_config_context()
    assert ctx.variables.get("SOME_VAR_NAME") == "hello"


def test_run_userconfig(top_dir, linux_docker, capfd):
    if "GLE_DOCKER_VOLUMES" in os.environ:
        del os.environ["GLE_DOCKER_VOLUMES"]
    os.environ["GLE_CONFIG"] = os.path.join(top_dir, "emulator", "configs", "example-emulator.yml")
    pipeline = os.path.join(top_dir, "emulator", "gitlabemu", "tests", "basic.yml")

    # create a temp dir that will be in our bound volume
    tempdir = tempfile.mkdtemp(dir=str(Path("/tmp")))
    try:
        runner.run(["-c", pipeline, "vars-job"])
        stdout, _ = capfd.readouterr()
        assert "SOME_VAR_NAME=\"hello\"" in stdout
        assert "EXECUTE_VARIABLE=\"ls -l /volume-mount\"" in stdout
        # only check for this on linux, mac rancher doesn't map to our real /tmp
        if platform.system() == "Linux":
            tempname = os.path.basename(tempdir)
            assert tempname in stdout
        assert "Build complete!" in stdout
    finally:
        shutil.rmtree(tempdir)


def test_illegal_context(caplog, tmp_path):
    os.environ["GLE_CONFIG"] = str(tmp_path / "foo.yml")
    os.environ["GLE_CONTEXT"] = "current_context"
    with pytest.raises(SystemExit):
        userconfig.get_current_user_context()
    assert "E!: 'current_context' is not allowed for GLE_CONFIG" in caplog.messages


def test_default_context(tmp_path):
    os.environ["GLE_CONFIG"] = str(tmp_path / "foo.yml")
    ctx = userconfig.get_current_user_context()
    assert ctx == "emulator"
