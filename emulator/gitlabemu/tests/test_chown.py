"""Test the chowner script"""
import os
import pytest
from ..chown import run


@pytest.mark.usefixtures("linux_only")
def test_chowner(in_tests: str) -> None:
    """Test the chown script"""
    run(args=[str(os.getuid()), str(os.getgid()), os.getcwd()])
