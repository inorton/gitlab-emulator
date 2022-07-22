import os
import pytest

TESTS_DIR = os.path.abspath(os.path.dirname(__file__))
EMULATOR_DIR = os.path.dirname(os.path.dirname(TESTS_DIR))


@pytest.fixture()
def specs_dir() -> str:
    return os.path.join(EMULATOR_DIR, "bamboo-specs")
