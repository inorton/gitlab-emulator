"""
Test the configloader
"""
import os

import pytest

import gitlabemu.errors
from .. import configloader
from .. import yamlloader
from ..docker import DockerJob

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

    top = loader.load_job("top")
    assert top.image == "baseimage:image"
    assert top.before_script[0] == "middle before_script"
    assert top.script[0] == "top script"
    assert top.variables
    assert "BASE" in top.variables
    assert "COLOR" in top.variables
    assert top.variables["BASE"] == "baseimage"
    assert top.variables["COLOR"] == "purple"

    last = loader.load_job("last")

    assert last.image == "busybox:latest"
    assert last.after_script == ["echo template-basic after_script"]
    assert last.before_script == top.before_script
    assert last.script == top.script


def test_missing_extends():
    """Test that extending a non-existing job does not hang"""
    loader = configloader.Loader()
    with pytest.raises(gitlabemu.errors.BadSyntaxError) as err:
        loader.load(os.path.join(HERE, "invalid", "extends-missing.yaml"))
    assert "Job 'job2' extends 'thing' which does not exist" in str(err.value)


def test_missing_script():
    """Test that forgetting to add script to a job raises an error"""
    loader = configloader.Loader()
    with pytest.raises(gitlabemu.errors.BadSyntaxError) as err:
        loader.load(os.path.join(HERE, "invalid", "script-missing.yaml"))
    assert "Job 'job' does not have a 'script' element." in str(err.value)


def test_inherit():
    """Test the inherit keyword"""
    loader = configloader.Loader()
    loader.load(os.path.join(HERE, "test-inherit.yaml"))

    job1: DockerJob = loader.load_job("job1")
    job2: DockerJob = loader.load_job("job2")
    job3: DockerJob = loader.load_job("job3")
    job4: DockerJob = loader.load_job("job4")
    job5: DockerJob = loader.load_job("job5")

    assert job1.image == "ruby:3.0"
    assert job1.before_script == ["df -h"]
    assert job1.variables["COLOR"] == "red"
    assert job2.image == "ruby:3.0"
    assert job2.before_script == []
    assert job2.variables["COLOR"] == "red"

    assert job3.image == job2.image
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
