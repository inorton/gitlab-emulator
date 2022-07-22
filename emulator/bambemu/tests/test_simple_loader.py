"""Test we can parse a spec folder"""
from ..loader import BamLoader


def test_load(specs_dir: str):
    loader = BamLoader()
    loader.load(specs_dir)

    plans = loader.get_plans()
    assert len(plans) == 1
    plan = plans[0]
    assert len(plan.jobs) == 2
    assert "list openssl" in plan.jobs
    assert "list markdown" in plan.jobs
    assert len(plan.repos) == 1

