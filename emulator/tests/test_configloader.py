"""
Test the configloader
"""
import os
from gitlabemu import configloader

HERE = os.path.dirname(__file__)
TOPDIR = os.path.dirname(os.path.dirname(HERE))


def test_loading_ci():
    loaded = configloader.read(os.path.join(TOPDIR, ".gitlab-ci.yml"))
    assert loaded


def test_load_extends():
    loaded = configloader.read(os.path.join(HERE, "test-extends.yaml"))

    job1 = loaded.get("job1")
    assert job1["image"] == "base1:image"
    assert job1["before_script"][0] == "base2"

    job2 = loaded.get("job2")
    assert "image" not in job2
    assert job2["before_script"][0] == "base2"
