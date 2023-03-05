import os
import pytest
from pathlib import Path
from _pytest.capture import CaptureFixture

from ..errors import BadSyntaxError
from ..runner import run

@pytest.mark.usefixtures("has_docker")
@pytest.mark.usefixtures("posix_only")
def test_include_processing(top_dir: str, capfd: CaptureFixture):
    os.chdir(top_dir)
    run(["skippy", "-c", "test-ci.yml"])
    stdout, stderr = capfd.readouterr()
    assert "STARSHIP_NAME=Flying Dutchman" in stdout
    assert "CREW_TYPE=monkeys" in stdout
    assert "MY_VARIABLE=" in stdout
    assert "BOOK=exforce" in stdout


def test_include_unknown(in_tests: str, capfd: CaptureFixture):
    with pytest.raises(SystemExit):
        run(["-c", str(Path("invalid") / "include-unknown-type.yaml"), "-l" ])
    stdout, stderr = capfd.readouterr()
    assert "FeatureNotSupportedError" in stderr
    assert "Do not understand how to include" in stderr


def test_include_twice(in_tests: str, capfd: CaptureFixture):
    with pytest.raises(SystemExit):
        run(["-c", str(Path("invalid") / "include-twice.yaml"), "-l"])
    stdout, stderr = capfd.readouterr()
    assert "empty.yaml has already been included" in stderr


def test_include_singular(in_tests: str, capfd: CaptureFixture):
    run(["-c", "test_include_singular.yaml", "-l"])
    stdout, stderr = capfd.readouterr()
    assert "jobname" in stdout
