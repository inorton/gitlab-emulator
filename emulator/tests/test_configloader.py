"""
Test the configloader
"""
import os

import pytest
from gitlabemu import configloader

HERE = os.path.dirname(__file__)
TOPDIR = os.path.dirname(os.path.dirname(HERE))


def test_loading_ci():
    loader = configloader.Loader()
    loader.load(os.path.join(TOPDIR, ".gitlab-ci.yml"))
    assert loader.config


def test_load_extends():
    loader = configloader.Loader()
    loader.load(os.path.join(HERE, "test-extends.yaml"))

    job1 = loader.get_job("job1")
    assert job1["image"] == "base1:image"
    assert job1["before_script"][0] == "base2"

    job2 = loader.get_job("job2")
    assert "image" not in job2
    assert job2["before_script"][0] == "base2"

    top = loader.get_job("top")

    assert top["image"] == "baseimage:image"
    assert top["before_script"][0] == "middle before_script"
    assert top["script"][0] == "top script"

    last = loader.get_job("last")

    assert last["image"] == "busybox:latest"
    assert last["after_script"] == ["echo template-basic after_script"]
    assert last["before_script"] == top["before_script"]
    assert last["script"] == top["script"]


def test_missing_extends():
    """Test that extending a non-existing job does not hang"""
    loader = configloader.Loader()
    with pytest.raises(configloader.BadSyntaxError) as err:
        loader.load(os.path.join(HERE, "invalid", "extends-missing.yaml"))
    assert "Job 'job2' extends 'thing' which does not exist" in str(err.value)
