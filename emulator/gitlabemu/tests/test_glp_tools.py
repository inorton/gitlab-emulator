"""Tests for glp"""
import os
from argparse import Namespace
from unittest.mock import Mock, ANY
import tempfile
import pytest
from pytest_mock import MockerFixture

from ..configloader import Loader
from ..gitlab_client_api import PipelineNotFound
from ..glp.tool import run
from ..glp.types import NameValuePair, Match, ArgumentTypeError


def test_help(capsys):
    """Test the help and usagle messages"""
    with pytest.raises(SystemExit) as err:
        run()
    assert err.value.code != 0
    _, stderr = capsys.readouterr()
    assert "invalid choice" in stderr
    assert "usage:" in stderr

    with pytest.raises(SystemExit):
        run(["--help"])
    stdout, _ = capsys.readouterr()
    assert "Gitlab Pipeline Tool" in stdout
    assert "{build,cancel,dump,export,jobs,list,subset}" in stdout

    for cmd in ["build", "list", "cancel", "dump", "export", "jobs", "subset"]:
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


def test_subset_command(repo_root: str, mocker: MockerFixture, mock_client_project_remote, tmp_path, capfd):
    """Test subset generation"""
    apic: Mock = mocker.patch("gitlabemu.gitlab_client_api.get_gitlab_project_client", autospec=True)
    client, project, remote = mock_client_project_remote
    apic.return_value = (client, project, remote)
    outfile = tmp_path / "dump.yml"
    # generate a single job subset with no deps and no from
    run(["subset", "quick", "-e", "SPEED=fast", "--dump", str(outfile)])
    assert outfile.exists()
    loader = Loader()
    loader.load(str(outfile))
    job = loader.load_job("quick")
    assert job
    outfile.unlink()

    # generate a subset with an artifact needed job
    run(["subset", "needs-artifacts", "--dump", str(outfile)])
    assert outfile.exists()
    loader = Loader()
    loader.load(str(outfile))
    quick = loader.load_job("quick")
    goal = loader.load_job("needs-artifacts")
    assert quick
    assert goal
    outfile.unlink()

    # generate a subset with an artifact needed job and a from pipeline
    # populate the mock client project
    # complain if no successful needed job exists
    pipeline = project.mock_add_pipeline()
    with pytest.raises(SystemExit):
        run(["subset", "--from", str(pipeline.id), "needs-artifacts", "--dump", str(outfile)])
    assert not outfile.exists()
    stdout, stderr = capfd.readouterr()
    assert "Pipeline did not contain a successful 'quick' job needed by needs-artifacts" in stderr

    # add a successful quick job
    job = pipeline.mock_add_job("quick", "success", [])
    job.artifacts.append({
        "file_type": "archive"
    })
    run(["subset", "--from", str(pipeline.id), "needs-artifacts", "--dump", str(outfile)])
    assert outfile.exists()
    loader = Loader()
    loader.load(str(outfile))
    quick = loader.load_job("quick")
    goal = loader.load_job("needs-artifacts")
    assert quick
    download_script = "\n".join(quick.script)

    assert f"{client.api_url}/projects/{project.id}/jobs/{job.id}/artifacts" in download_script

    assert goal

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


def test_export_tool(mocker, capsys):
    """Test the export command"""

    export_cmd: Mock = mocker.patch("gitlabemu.glp.exporttool.export_cmd", autospec=True)

    run(["export", "1234", "folder"])
    export_cmd.assert_called_with("1234", "folder",
                                  exec_export=None,
                                  tls_verify=True)

    run(["export", "2345", "folder", "job1", "--", "--exec", "ls", "-l", "%p"])
    export_cmd.assert_called_with("2345", "folder", "job1",
                                  exec_export=["ls", "-l", "%p"],
                                  tls_verify=True)
