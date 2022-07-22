"""
Test the configloader
"""
import os

import pytest

import gitlabemu.types
from .. import configloader
from .. import yamlloader

HERE = os.path.dirname(__file__)
TOPDIR = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def test_references():
    loader = configloader.Loader()
    loader.load(os.path.join(HERE, "references.yaml"))
    assert loader.config

    assert loader.config["job1"]["variables"]["COLOR"] == "red"
    assert loader.config["job1"]["script"] == [
        "uname -a",
        "date",
        "df -h",
        "pwd > pwd.txt"
    ]
    assert loader.config["job1"]["artifacts"]["paths"] == ["pwd.txt"]

    assert loader.config["job2"]["variables"] == {
        "COLOR": "red",
        "SHAPE": "triangle"
    }


def test_bad_references():
    loader = configloader.Loader()
    with pytest.raises(yamlloader.ReferenceError) as err:
        loader.load(os.path.join(HERE, "invalid", "bad_references.yaml"))

    assert "cannot find referent job for !reference [.template, variables, COLOR]" in err.value.message
    assert "bad_references.yaml\", line 4, column 12" in err.value.message

    loader = configloader.Loader()
    with pytest.raises(yamlloader.ReferenceError) as err:
        loader.load(os.path.join(HERE, "invalid", "bad_references_2.yaml"))

    assert "cannot find referent key for !reference [.template, variables, COLOR]" in err.value.message
    assert "bad_references_2.yaml\", line 7, column 12" in err.value.message

    loader = configloader.Loader()
    with pytest.raises(yamlloader.ReferenceError) as err:
        loader.load(os.path.join(HERE, "invalid", "bad_references_3.yaml"))

    assert "cannot find referent value for !reference [.template, variables, COLOR]" in err.value.message
    assert "bad_references_3.yaml\", line 8, column 12" in err.value.message


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
    assert top["variables"]
    assert "BASE" in top["variables"]
    assert "COLOR" in top["variables"]
    assert top["variables"]["BASE"] == "baseimage"
    assert top["variables"]["COLOR"] == "purple"

    last = loader.get_job("last")

    assert last["image"] == "busybox:latest"
    assert last["after_script"] == ["echo template-basic after_script"]
    assert last["before_script"] == top["before_script"]
    assert last["script"] == top["script"]


def test_missing_extends():
    """Test that extending a non-existing job does not hang"""
    loader = configloader.Loader()
    with pytest.raises(gitlabemu.types.BadSyntaxError) as err:
        loader.load(os.path.join(HERE, "invalid", "extends-missing.yaml"))
    assert "Job 'job2' extends 'thing' which does not exist" in str(err.value)
