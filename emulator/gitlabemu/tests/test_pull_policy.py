import subprocess

import pytest
from ..runner import run

CI_FILE = "test_pull_policy.yml"

@pytest.mark.usefixtures("posix_only")
@pytest.mark.usefixtures("has_docker")
def test_ci_never_pull(in_tests, caplog):
    with pytest.raises(SystemExit):
        run(["-c", CI_FILE, "job2"])
    messages = caplog.messages
    assert "E!: Docker image docker.io/no-such-image/exists:latest does not exist, (pull_policy=never)" in messages

@pytest.mark.usefixtures("posix_only")
@pytest.mark.usefixtures("has_docker")
def test_override_pull(in_tests, caplog):
    with pytest.raises(SystemExit):
        run(["-c", CI_FILE, "job2", "--docker-pull=if-not-present"])
    messages = caplog.messages
    assert "E!: cannot pull image: docker.io/no-such-image/exists:latest - image not found" in messages

    subprocess.call(["docker", "image", "rm", "local_tagged_alpine:latest"])
    with pytest.raises(SystemExit):
        run(["-c", CI_FILE, "job1", "--docker-pull=never"])
    messages = caplog.messages
    assert "E!: Docker image local_tagged_alpine:latest does not exist, (pull_policy=never)" in messages

    subprocess.check_call(["docker", "pull", "alpine:latest"])
    subprocess.check_call(["docker", "tag", "alpine:latest", "local_tagged_alpine:latest"])
    run(["-c", CI_FILE, "job1", "--docker-pull=never"])
