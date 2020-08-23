"""
Test the configloader
"""
import os
import pytest

from gitlabemu import configloader

HERE = os.path.dirname(__file__)


def test_loading_ci():
    loaded = configloader.read(os.path.join(os.path.dirname(HERE), ".gitlab-ci.yml"))
    assert loaded
