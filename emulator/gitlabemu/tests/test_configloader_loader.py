"""
Test the object based loader interface
"""
import os
from .. import configloader

HERE = os.path.dirname(__file__)


def test_load_simple(top_dir):
    loader = configloader.Loader()
    yamlfile = os.path.join(top_dir, ".gitlab-ci.yml")
    expected = configloader.read(yamlfile)

    loader.load(yamlfile)

    assert loader.config == expected


def test_load_callbacks(top_dir):
    loader = configloader.Loader()
    yamlfile = os.path.join(top_dir, ".gitlab-ci.yml")
    loader.load(yamlfile)

    assert loader.config
    assert loader.filename == ".gitlab-ci.yml"
    assert len(loader.included_files) == 3
    assert loader.get_stages() == ["build", "test"]
    assert loader.get_job_filename("check-alpine") == "ci-includes/subdir/jobs.yml"
    assert loader.get_job_filename(".alpine-image") == "ci-includes/alpine-image.yml"
    assert loader.get_job_filename(".fail-job") == ".gitlab-ci.yml"
