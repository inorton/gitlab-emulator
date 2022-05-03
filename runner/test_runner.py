"""
Tests for the runner
"""
from GitlabPyRunner.executor import run


def test_register(random_runner):
    """
    Test that we can register and unregister a runner
    :return:
    """
    assert random_runner.token


def test_poll_none(random_runner):
    """
    Poll for a job, we should not get one because we use a random runner tag
    :param random_runner:
    :return:
    """
    job = random_runner.poll()
    assert not job


def test_poll_manual(playground_runner):
    """
    Run a real job
    :param playground_runner:
    :return:
    """
    job = playground_runner.poll()
    assert job
    assert run(playground_runner, job, False)
    playground_runner.success(job)


