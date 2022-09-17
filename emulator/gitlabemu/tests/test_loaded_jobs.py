"""Test loaded job objects"""
import os
from .. import configloader


def test_load_expected(top_dir):
    loader = configloader.Loader()
    yamlfile = os.path.join(top_dir, ".gitlab-ci.yml")
    loader.load(yamlfile)

    job = loader.load_job("emulator-linux-test_py3.10")
    assert job.artifacts
    assert job.artifacts.when == "always"
    assert job.artifacts.paths == []
    assert not job.artifacts.name
    assert job.artifacts.reports
    assert job.artifacts.reports["junit"] == ["emulator/test-results.xml"]
    assert job.artifacts.reports["coverage_report"] == {
        "coverage_format": "cobertura",
        "path": "emulator/pytest-coverage.xml"
    }

    quick = loader.load_job("quick")
    assert quick.artifacts
    assert quick.artifacts.paths == ["date.txt"]
