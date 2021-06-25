"""
Test -i and --before-script
"""
import os
from gitlabemu import runner

TOPDIR = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
TOPCFG = os.path.join(TOPDIR, ".gitlab-ci.yml")


def test_interactive_starts_before(linux_docker, capfd):
    runner.run(["-i", "-b", "-c", TOPCFG, ".check-interactive"])
    stdout, stderr = capfd.readouterr()

    assert "hello-stderr" in stderr
    assert "Running before_script.." in stdout
    assert "CI_FOO=hello" in stdout
    assert "++ done ++" in stdout
    assert "Exiting shell" in stdout


def test_interactive_starts(linux_docker, capfd):
    runner.run(["-i", "-c", TOPCFG, ".check-interactive"])
    stdout, stderr = capfd.readouterr()

    assert "hello-stderr" not in stderr
    assert "Running before_script.." not in stdout
    assert "Exiting shell" in stdout