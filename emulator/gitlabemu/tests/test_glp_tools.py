"""Tests for glp"""
import os
from argparse import Namespace
from unittest.mock import Mock, ANY
import tempfile
import pytest
from pytest_mock import MockerFixture

from ..gitlab_client_api import PipelineNotFound
from ..glp.tool import run
from ..glp.types import NameValuePair, Match, ArgumentTypeError


def test_help(capsys):
    """Test the help and usagle messages"""
    with pytest.raises(SystemExit) as err:
        run()
    assert err.value.code != 0
    _, stderr = capsys.readouterr()
    assert "error: invalid choice" in stderr
    assert "usage:" in stderr

    with pytest.raises(SystemExit):
        run(["--help"])
    stdout, _ = capsys.readouterr()
    assert "Gitlab Pipeline Tool" in stdout
    assert "{list,cancel,build,subset,jobs}" in stdout

    for cmd in ["list", "cancel", "build", "subset"]:
        with pytest.raises(SystemExit):
            run([cmd, "--help"])


def test_bad_arg_types(capsys):
    """Test the argparse validators"""
    with pytest.raises(ArgumentTypeError):
        NameValuePair("foo")
    with pytest.raises(ArgumentTypeError):
        NameValuePair("bar=")
    with pytest.raises(ArgumentTypeError):
        NameValuePair("=foo")

    with pytest.raises(ArgumentTypeError) as err:
        Match("cat=dog")
    assert "'cat' is not one of " in err.value.args[0]


def test_build_vars(mocker: MockerFixture):
    """Test -e VAR=VALUE"""

    create: Mock = mocker.patch("gitlabemu.glp.buildtool.create_pipeline", autospec=True)

    run(["build", "-e", "COLOR=red"])

    create.assert_called_once_with(
        vars={"COLOR": "red"},
        tls_verify=True,
    )


def test_subset_command(repo_root: str, mocker: MockerFixture):
    """Test subset generation"""
    generate: Mock = mocker.patch("gitlabemu.glp.subsettool.generate_pipeline", autospec=True)

    run(["subset", "quick", "-e", "SPEED=fast"])

    generate.assert_called_once_with(
        ANY,
        "quick",
        vars={"SPEED": "fast"},
        use_from=None,
        tls_verify=True
    )


def test_list_command(mocker: MockerFixture):
    """Test list and matcher passing"""
    pipelines_cmd = mocker.patch("gitlabemu.glp.listtool.pipelines_cmd", autospec=True)

    run(["list", "--limit", "17"])
    pipelines_cmd.assert_called_with(
        matchers={},
        limit=17,
        tls_verify=True,
        do_list=True
    )

    run(["list", "--match", "status=pending"])
    pipelines_cmd.assert_called_with(
        matchers={"status": "pending"},
        limit=10,
        tls_verify=True,
        do_list=True
    )


def test_cancel_tool(mocker: MockerFixture):
    """Test cancel and its matchers"""
    pipelines_cmd = mocker.patch("gitlabemu.glp.canceltool.pipelines_cmd", autospec=True)
    run(["cancel", "--match", "status=pending"])
    pipelines_cmd.assert_called_with(
        matchers={"status": "pending"},
        limit=10,
        tls_verify=True,
        do_cancel=True
    )


@pytest.mark.usefixtures("posix_only")
def test_jobs_tool(capsys, mocker: MockerFixture):
    with pytest.raises(SystemExit):
        run(["jobs", "--help"])
    stdout, stderr = capsys.readouterr()
    assert "List pipeline jobs" in stdout

    with tempfile.TemporaryDirectory() as path:
        os.chdir(path)
        with pytest.raises(SystemExit) as err:
            run(["jobs"])

        assert err.value.code != 0
        stdout, stderr = capsys.readouterr()
        assert "has no remotes" in stderr
        assert "is it a git repo?" in stderr
        project = mocker.Mock()
        pipeline = mocker.Mock()
        project.pipelines.list.return_value = []
        mocker.patch("gitlabemu.glp.jobstool.git_current_branch", return_value="main")
        mocker.patch("gitlabemu.glp.jobstool.get_current_project_client", return_value=(None, project, "origin"))

        with pytest.raises(PipelineNotFound):
            run(["jobs"])

        project.pipelines.list.return_value = [pipeline]
        pipeline.jobs.list.return_value = [Namespace(name="job1", status="complete")]
        _, _ = capsys.readouterr()

        run(["jobs"])
        stdout, stderr = capsys.readouterr()
        assert "Searching for most recent pipeline on branch: main" in stderr
        assert "job1" in stdout
