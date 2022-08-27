"""Test the glp dump command"""
import os

from ..glp.tool import run

def test_dump_all(repo_root: str):
    """Test we can dump the gle project config"""
    os.chdir(repo_root)
    run(["dump"])


def test_dump_jobs(repo_root: str):
    """Test we can dump a job from the gle project config"""
    os.chdir(repo_root)
    run(["dump", "quick"])
    run(["dump", "quick", "git-alpine"])


def test_dump_services(repo_root: str):
    """Test dumping jobs with services"""
    os.chdir(os.path.join(repo_root, "emulator", "gitlabemu", "tests"))
    run(["dump", "-c", "test-services.yaml"])
