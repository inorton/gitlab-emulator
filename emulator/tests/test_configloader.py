"""
Test the configloader
"""
import os
from gitlabemu import configloader

HERE = os.path.dirname(__file__)
TOPDIR = os.path.dirname(os.path.dirname(HERE))


def test_loading_ci():
    """
    Test loading the standard top level file
    :return:
    """
    loader = configloader.Loader()
    loader.load(os.path.join(TOPDIR, ".gitlab-ci.yml"))


def test_load_extends():
    loader = configloader.Loader()
    loader.load(os.path.join(HERE, "test-extends.yaml"))

    job1 = loader.get_job("job1")
    assert job1["image"] == "base1:image"
    assert job1["before_script"][0] == "base2"

    job2 = loader.get_job("job2")
    assert "image" not in job2
    assert job2["before_script"][0] == "base2"
