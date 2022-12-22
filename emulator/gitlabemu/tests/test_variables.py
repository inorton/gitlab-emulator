"""Test proper variable expansion"""
import pytest
from ..runner import run

@pytest.mark.usefixtures("has_docker")
@pytest.mark.usefixtures("posix_only")
def test_expand(in_tests, capfd):
    run(["-c", "test-variables.yml", "book"])
    stdout, _ = capfd.readouterr()
    lines = stdout.splitlines()

    assert "SHAPE=Circle" in lines
    assert "TITLE=The Magic Circle" in lines
    assert "ID_TEMPLATE=build-$CI_PIPELINE_ID" in lines
    assert "BUILD_ID=book build-0" in lines