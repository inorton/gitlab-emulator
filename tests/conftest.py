import sys
import os
import pytest
HERE = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, HERE)


@pytest.fixture(scope="function")
def tests_dir():
    os.chdir(os.path.dirname(__file__))
    return os.getcwd()
