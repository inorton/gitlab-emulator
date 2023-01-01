"""
Test the object based loader interface
"""
import os
from typing import Any, Dict

import pytest

from .. import configloader
from ..configloader import ValidatorMixin
from ..errors import BadSyntaxError, ConfigLoaderError
from ..runner import run

HERE = os.path.dirname(__file__)


def test_load_simple(top_dir):
    loader = configloader.Loader()
    yamlfile = os.path.join(top_dir, ".gitlab-ci.yml")
    configloader.read(yamlfile)
    loader.load(yamlfile)


def test_load_callbacks(top_dir):
    loader = configloader.Loader()
    yamlfile = os.path.join(top_dir, ".gitlab-ci.yml")
    loader.load(yamlfile)

    assert loader.config
    assert loader.filename == ".gitlab-ci.yml"
    assert len(loader.included_files) == 3
    assert loader.get_stages() == ["build", "test", "last"]
    assert loader.get_job_filename("check-alpine") == "ci-includes/subdir/jobs.yml"
    assert loader.get_job_filename(".alpine-image") == "ci-includes/alpine-image.yml"
    assert loader.get_job_filename(".fail-job") == ".gitlab-ci.yml"


def test_real_extends(top_dir, linux_docker, capsys):
    os.chdir(top_dir)
    run(["extends-checker_1"])
    stdout, stderr = capsys.readouterr()

    assert "SPEED=fast" in stdout
    assert "FRUIT=orange" in stdout

    run(["extends-checker_2"])
    stdout, stderr = capsys.readouterr()

    assert "SPEED=warp" in stdout
    assert "FRUIT=orange" in stdout


def test_validate_mixin_artifacts():
    validator = ValidatorMixin()
    config: Dict[str, Any] = {
        "job": {
            "stage": "test",
            "script": ["echo"],
            "artifacts": {
                "paths":
                    [
                        "*.txt"
                    ],
                "reports": {
                    "junit": [
                        "test-results.xml"
                    ]
                }
            }
        }
    }
    validator.validate(config)

    # check missing script
    config["job2"] = {
        "image": "test:stuff"
    }
    with pytest.raises(BadSyntaxError) as err:
        validator.validate(config)
    assert "'job2' does not have a 'script' element" in str(err.value)
    # check script missing allowed for trigger jobs
    config["job2"]["trigger"] = {
        "project": "foo/bar",
        "branch": "main"
    }
    validator.validate(config)

    # check no artifacts are permitted
    del config["job"]["artifacts"]
    validator.validate(config)

    # check bad artifacts and paths
    config["job"]["artifacts"] = {
        "paths": "foo"
    }
    with pytest.raises(ConfigLoaderError) as err:
        validator.validate(config)
    assert "artifacts->paths must be a list" in str(err.value)

    config["job"]["artifacts"] = {
        "reports": "foo"
    }
    with pytest.raises(ConfigLoaderError) as err:
        validator.validate(config)
    assert "artifacts->reports must be a map" in str(err.value)

