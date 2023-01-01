import os
import uuid
import pytest
from pathlib import Path
from ..gitlab_client_api import get_ca_bundle

@pytest.mark.usefixtures("posix_only")
def test_ca_bundle_reader(temp_folder: Path):
    one = temp_folder / "one.txt"
    magic = str(uuid.uuid4())
    with open(one, "w") as one_fd:
        print(f"cert-one-{magic}", file=one_fd)
    os.environ["REQUESTS_CA_BUNDLE"] = str(one.absolute())

    certs = get_ca_bundle()
    assert f"cert-one-{magic}" in certs
