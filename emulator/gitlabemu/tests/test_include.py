import os

import pytest
from _pytest.capture import CaptureFixture
from ..runner import run

@pytest.mark.usefixtures("has_docker")
def test_include_processing(top_dir: str, capfd: CaptureFixture):
    os.chdir(top_dir)
    run(["skippy", "-c", "test-ci.yml"])
    stdout, stderr = capfd.readouterr()
    assert "STARSHIP_NAME=Flying Dutchman" in stdout
    assert "CREW_TYPE=monkeys" in stdout
    assert "MY_VARIABLE=" in stdout
    assert "BOOK=exforce" in stdout

