"""
Test the configloader
"""
import os

import pytest

from .. import configloader
from .. import yamlloader
from ..errors import BadSyntaxError, ConfigLoaderError

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


def test_missing_script():
    """Test that forgetting to add script to a job raises an error"""
    loader = configloader.Loader()
    with pytest.raises(BadSyntaxError) as err:
        loader.load(os.path.join(HERE, "invalid", "script-missing.yaml"))
    assert "Job 'job' does not have a 'script' element." in str(err.value)


def test_missing_needs():
    loader = configloader.Loader()
    with pytest.raises(ConfigLoaderError) as err:
        loader.load(os.path.join(HERE, "invalid", "needs-missing.yaml"))
    assert "job job1 needs job job0 which does not exist" in str(err.value)


def test_missing_stage():
    loader = configloader.Loader()
    with pytest.raises(ConfigLoaderError) as err:
        loader.load(os.path.join(HERE, "invalid", "stage-missing.yaml"))
    assert "job job1 has stage fish which does not exist" in str(err.value)
