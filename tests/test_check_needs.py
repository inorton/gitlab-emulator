import pytest

from gitlabemu import runner


def test_run_needs(tests_dir):
    runner.run(["--config", "test-needs.yaml", "--full", "finish"])
