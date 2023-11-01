"""Tests for helpers.py"""
import os
import sys
from typing import Dict

import pytest
import subprocess
import uuid
from io import StringIO
from ..helpers import (
    clean_leftovers,
    communicate,
    get_git_remote_urls,
    git_commit_sha,
    git_current_branch,
    git_uncommitted_changes,
    git_worktree,
    is_apple,
    make_path_slug,
    parse_timeout,
    plausible_docker_volume,
    remote_servers,
    sensitive_varname,
    setenv_string,
    trim_quotes, )
from ..variables import truth_string
from ..logmsg import debug_enabled


@pytest.mark.usefixtures("posix_only")
def test_communicate() -> None:
    magic = str(uuid.uuid4())
    script = f"echo '{magic}'\n".encode()
    output = StringIO()
    proc = subprocess.Popen(["/bin/sh", "-"], shell=False,
                            stdin=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            stdout=subprocess.PIPE
                            )

    communicate(proc, stdout=output, script=script)

    output.seek(0)
    content = output.read()

    assert magic in content


@pytest.mark.usefixtures("posix_only")
def test_communicate_throws() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(1)"], shell=False,
                            stderr=subprocess.STDOUT,
                            stdout=subprocess.PIPE
                            )
    with pytest.raises(subprocess.CalledProcessError):
        communicate(proc, script=None, throw=True)


@pytest.mark.usefixtures("has_docker")
@pytest.mark.usefixtures("posix_only")
def test_clean():
    clean_leftovers()


def test_debug_enabled():
    for enabled in ["y", "yes", "1"]:
        os.environ["GLE_DEBUG"] = enabled
        assert debug_enabled()

    for negative in ["0", "no", "moose", str(uuid.uuid4())]:
        os.environ["GLE_DEBUG"] = negative
        assert not debug_enabled()


def test_make_path_slug():
    assert "Foo_Bar_123" == make_path_slug("Foo/Bar 123")


def test_decode_volume_line():
    simple = plausible_docker_volume("/home:/mnt")
    assert simple.host == "/home"
    assert simple.mount == "/mnt"
    assert simple.mode == "rw"

    assert str(simple) == "/home:/mnt:rw"

    vanilla = plausible_docker_volume("/home/user:/mnt/home/user:ro")
    assert vanilla.host == "/home/user"
    assert vanilla.mount == "/mnt/home/user"
    assert vanilla.mode == "ro"

    stripped = plausible_docker_volume("/home/:/mnt/home/:rw")
    assert stripped.host == "/home"
    assert stripped.mount == "/mnt/home"
    assert stripped.mode == "rw"

    windows = plausible_docker_volume('c:\\foo\\bar:c:\\path\\bar')
    assert windows.host == 'c:\\foo\\bar'
    assert windows.mount == 'c:\\path\\bar'
    assert windows.mode == 'rw'

    windows_mode = plausible_docker_volume('c:\\windows\\temp\\:c:\\outside\\temp:ro')
    assert windows_mode.host == 'c:\\windows\\temp'
    assert windows_mode.mount == 'c:\\outside\\temp'
    assert windows_mode.mode == 'ro'

    nonsense = plausible_docker_volume("/foo")
    assert nonsense is None


def test_trim_quotes():
    assert trim_quotes('"foo bar"') == 'foo bar'
    assert trim_quotes('\'foo bar\'') == 'foo bar'
    assert trim_quotes('trailing_quote\"') == "trailing_quote\""
    assert trim_quotes('\"mismatched\'') == '\"mismatched\''
    assert trim_quotes("") == ""


def test_sensitive_varnames():
    assert sensitive_varname("MY_PASSWORD")
    assert sensitive_varname("SECRET_TOKEN")
    assert sensitive_varname("PRIVATE_KEY")

    assert not sensitive_varname("PATH")
    assert not sensitive_varname("USERNAME")


@pytest.mark.usefixtures("linux_only")
def test_platforms():
    assert not is_apple()


def test_parse_timeout_str():
    assert parse_timeout("1m") == 60

    with pytest.raises(ValueError) as err:
        parse_timeout("1 m")
    assert "Cannot decode timeout 1 m" in err.value.args

    with pytest.raises(ValueError) as err:
        parse_timeout("x")
    assert "Cannot decode timeout x" in err.value.args

    with pytest.raises(ValueError) as err:
        parse_timeout("1h 2h")
    assert "Unexpected h value 1h 2h" in err.value.args


def test_git_helpers(top_dir: str):
    remotes = get_git_remote_urls(top_dir)
    assert isinstance(remotes, dict)
    assert len(remotes)

    commit = git_commit_sha(top_dir)
    assert commit
    assert len(commit) >= 40

    branch = git_current_branch(top_dir)
    assert branch

    # just check that they don't crash, can't get relaible values from these locally and on CI runs
    git_uncommitted_changes(top_dir)
    git_worktree(top_dir)


@pytest.mark.parametrize(["remotes", "expected_servers"], [
    (
            {"origin": "https://my.git.server/my/repo"},
            {"origin": "my.git.server/my/repo"},
    ),
    (
            {"origin": "git@my.git.server:my/repo.git"},
            {"origin": "my.git.server/my/repo"},
    )
])
def test_parse_remote_servers(remotes: Dict[str, str], expected_servers: [Dict[str, str]]):
    servers = remote_servers(remotes)
    assert servers == expected_servers


def test_argparse_helpers():
    with pytest.raises(ValueError):
        setenv_string("foo")
    name, value = setenv_string("foo=bar")
    assert name == "foo"
    assert value == "bar"


def test_truth_string_helper():
    assert truth_string("y")
    assert truth_string("1")
    assert truth_string("Y")
    assert truth_string("true")
    assert truth_string("yes")
    assert truth_string("Yes")
    assert truth_string("on")
    assert not truth_string("off")
    assert not truth_string("false")
    assert not truth_string("None")
