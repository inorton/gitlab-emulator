"""Test that various ci configs execute rules"""
import os
from pathlib import Path

import pytest

from ...configloader import Loader

HERE = Path(__file__).parent

def test_file_not_included_by_default():
    """Test that a condtional include is skipped when no rule matches"""
    loader = Loader()
    basic = HERE / "basic_job_rules"
    loader.rootdir = str(basic)
    loader.load(str(basic / ".gitlab-ci.yml"))
    jobs = loader.get_jobs()
    assert "job" in jobs
    assert "only_red" in jobs
    assert "green" not in jobs


def test_file_included_by_rule():
    """Test that a condtional include is skipped when no rule matches"""
    loader = Loader()
    loader.add_variable("INCLUDE", "colors")

    basic = HERE / "basic_job_rules"
    loader.rootdir = str(basic)
    loader.load(str(basic / ".gitlab-ci.yml"))
    jobs = loader.get_jobs()
    assert "job" in jobs
    assert "only_red" in jobs
    assert "green" in jobs

