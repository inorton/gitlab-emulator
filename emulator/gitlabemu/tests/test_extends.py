import os

import pytest
from pathlib import Path

from .test_configloader import HERE
from .. import configloader
from ..runner import run

INVALID_DIR = Path(__file__).parent / "invalid"


def test_extends_self(in_tests: str, capfd) -> None:
    extends_self = INVALID_DIR / "extends-self.yaml"
    with pytest.raises(SystemExit):
        run(["-c", str(extends_self), "-l"])
    _, stderr = capfd.readouterr()
    assert "Config error: Job 'job' cannot extend itself" in stderr


def test_extends_missing(in_tests: str, capfd) -> None:
    extends_self = INVALID_DIR / "extends-missing.yaml"
    with pytest.raises(SystemExit):
        run(["-c", str(extends_self), "-l"])
    _, stderr = capfd.readouterr()
    assert "Config error: Job 'job2' extends 'thing' which does not exist" in stderr


def test_load_extends():
    loader = configloader.Loader()
    loader.load(os.path.join(HERE, "test_extends.yaml"))

    job1 = loader.get_job("job1")
    assert job1["image"] == "base1:image"
    assert job1["before_script"][0] == "base2"

    job2 = loader.get_job("job2")
    assert "image" not in job2
    assert job2["before_script"][0] == "base2"

    top = loader.load_job("top")
    assert top.docker_image == "baseimage:image"
    assert top.before_script[0] == "middle before_script"
    assert top.script[0] == "top script"
    assert top.variables
    assert "BASE" in top.variables
    assert "COLOR" in top.variables
    assert top.variables["BASE"] == "baseimage"
    assert top.variables["COLOR"] == "purple"

    last = loader.load_job("last")

    assert last.docker_image == "busybox:latest"
    assert last.after_script == ["echo template-basic after_script"]
    assert last.before_script == top.before_script
    assert last.script == top.script
