"""
Test the object based loader interface
"""
import os
from .. import configloader
from ..runner import run

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
