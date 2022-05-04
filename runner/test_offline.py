"""
Test functions of the runner without a server
"""
import os
import platform
import stat
from contextlib import contextmanager

import pytest
from gitlabemu.helpers import is_windows
from GitlabPyRunner.runner import Runner
from GitlabPyRunner.executor import archive, run
from GitlabPyRunner.trace import TraceProxy


class FakeTrace(object):
    def writeline(self, msg):
        print(msg)

    @contextmanager
    def section(self, section, header):
        print(header)
        yield


def test_unpack_permissions(capsys, tmpdir):
    """
    Test that execute permissions are restored on unpacking artifacts
    """
    shellscript = (tmpdir / "file.sh").strpath
    with open(shellscript, "w") as sf:
        sf.write("#!/bin/sh\n")
        sf.write("set -e\n")
        sf.write("echo hello\n")
    os.chmod(shellscript, 0o755)

    zippath = archive(FakeTrace(),
                      {
                          "job": {
                              "artifacts": {
                                  "paths": [
                                      "file.sh"
                                  ],
                                  "name": "job"
                              }
                          }
                      },
                      "job",
                      tmpdir.strpath,
                      os.path.dirname(shellscript),
                      True)

    captured = capsys.readouterr()
    assert "finding file.sh" in captured.out
    assert shellscript in captured.out
    os.unlink(shellscript)

    runner = Runner(None, "token")
    runner.unpack_dependencies(FakeTrace(), zippath, tmpdir.strpath)
    unpacked = os.path.join(tmpdir.strpath, "file.sh")
    assert os.path.exists(unpacked)
    if not is_windows():
        stats = os.stat(unpacked)
        assert stats
        mode = stat.S_IMODE(stats.st_mode)
        assert mode & stat.S_IXUSR  # owner has execute

    captured = capsys.readouterr()

    assert captured
    assert "Unpacking artifacts into {}..".format(tmpdir.strpath) in captured.out


def compute_server_job(name=".computed", script=None):
    if script is None:
        script = ["echo hello"]

    job = {
        "variables": [
            {
                "key": "GITLAB_PYTHON_RUNNER_COMPUTED",
                "value": "yes",
            },
            {
                "key": "CI_PROJECT_PATH",
                "value": "testing/runner"
            },
            {
                "key": "CI_COMMIT_REF",
                "value": "main"
            },
            {
                "key": "CI_CONFIG_PATH",
                "value": ".gitlab-ci.yml"
            }
        ],
        "git_info": {
            "repo_url": "https://gitlab.com/cunity/gitlab-emulator.git"
        },
        "job_info": {
            "name": name,
        },
        "stage": "test",
        "image": None,
        "dependencies": [],
        "services": [],
        "steps": [
            {
                "name": "script",
                "script": script
            }
        ]
    }

    return job


class SimpleTrace(TraceProxy):

    def __init__(self):
        self.messages = []

    def flush(self):
        pass

    def write(self, text, flush=False):
        self.messages.append(text.decode())
        print("TRACE: {}".format(text.decode()))

    def trace(self, trace, text, offset=0):
        self.write(text)

    def __str__(self):
        ret = ""
        for item in self.messages:
            ret += item
        return ret

    def assert_contains(self, needle):
        __tracebackhide__ = True
        text = str(self)
        if needle not in text:
            pytest.fail("could not find '{}' in:\n{}".format(needle, text))

    def assert_not_contains(self, needle):
        __tracebackhide__ = True
        text = str(self)
        if needle in text:
            pytest.fail("found '{}' in:\n{}".format(needle, text))


@pytest.mark.timeout(60)
def test_runner_run_offline():
    # test the default shell
    ls = "ls"
    if platform.system() == "Windows":
        ls = "dir"
    runner = Runner(None, None)
    trace = SimpleTrace()
    runner.trace = trace.trace
    job = compute_server_job(script=["echo 'job start'", ls, "echo hello"])
    result = run(runner, job, False)

    trace.assert_contains("README.md")
    assert result, str(trace)


@pytest.mark.timeout(60)
def test_runner_run_powershell():
    if not platform.system() == "Windows":
        pytest.skip("Windows only")

    runner = Runner(None, None)
    runner.shell = "powershell"
    trace = SimpleTrace()
    runner.trace = trace.trace
    job = compute_server_job(script=["echo hello", "Get-ChildItem *.md"])
    result = run(runner, job, False)

    trace.assert_contains("README.md")
    trace.assert_contains("Directory:")
    assert result, str(trace)


@pytest.mark.timeout(60)
def test_runner_run_cmd():
    if not platform.system() == "Windows":
        pytest.skip("Windows only")

    runner = Runner(None, None)
    runner.shell = "cmd"
    trace = SimpleTrace()
    runner.trace = trace.trace
    job = compute_server_job(script=[
        "ping 127.0.0.1 -n 3",
        "echo hello",
        "dir /W /X *.md",
        "exit"
    ])
    result = run(runner, job, False)

    trace.assert_contains("Volume in drive")
    trace.assert_contains("README.md")
    trace.assert_not_contains("----")
    assert result, str(trace)


@pytest.mark.timeout(60)
def test_runner_run_fail_cmd():
    if not platform.system() == "Windows":
        pytest.skip("Windows only")

    runner = Runner(None, None)
    runner.shell = "cmd"
    trace = SimpleTrace()
    runner.trace = trace.trace
    job = compute_server_job(script=["echo hello", "dir moose-not-found || exit /b", "echo lemons"])
    result = run(runner, job, False)

    trace.assert_contains("hello")
    trace.assert_not_contains("----")
    trace.assert_not_contains("lemons")
    assert not result, str(trace)


@pytest.mark.timeout(60)
def test_runner_run_offline_fail_powershell():
    if not platform.system() == "Windows":
        pytest.skip("Windows only")
    runner = Runner(None, None)
    runner.shell = "powershell"
    trace = SimpleTrace()
    runner.trace = trace.trace
    job = compute_server_job(script=[
        "dir",
        "echo hello",
        "not a real program",
        "should not happen",
    ])
    result = run(runner, job, False)

    trace.assert_contains("hello")
    trace.assert_not_contains("should not happen")
    assert not result, str(trace)
