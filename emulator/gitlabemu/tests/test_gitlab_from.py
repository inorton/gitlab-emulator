"""Test the --from options"""
import os

import pytest
import argparse
from ..runner import do_gitlab_from, run, ProjectPipelineJob

@pytest.mark.usefixtures("posix_only")
def test_from_missing_download_args(capsys):
    with pytest.raises(SystemExit):
        do_gitlab_from(argparse.Namespace(FROM=None, download=True), None, None)

    _, stderr = capsys.readouterr()
    assert "--download requires --from PIPELINE" in stderr


@pytest.mark.usefixtures("posix_only")
def test_mock_download(capsys, top_dir: str, mocker):
    os.chdir(top_dir)
    os.environ["GITLAB_PRIVATE_TOKEN"] = "123"
    gl = mocker.patch("gitlabemu.runner.Gitlab")
    gl.projects = {}
    run(["-k", "--download", "emulator-linux-test", "--from", "gitlab.none/group/project/1234"])
    _, stderr = capsys.readouterr()
    assert "TLS server validation disabled" in stderr
    assert "Download 'emulator-linux-test' artifacts" in stderr

    # now mock get_pipeline()
    pipe = mocker.MagicMock()
    pipe.jobs = mocker.MagicMock()

    class FakeJob:
        def __init__(self, name):
            self.id = 3128
            self.name = name
            self.api_url = "http://foo"

    class FakeProject:
        def __init__(self):
            self.id = 1

    def get_jobslist(*args, **kwargs):
        return [FakeJob("emulator-linux-test")]
    pipe.jobs.list = mocker.MagicMock(side_effect=get_jobslist)

    zipfile = mocker.patch("gitlabemu.runner.zipfile.ZipFile", autospec=True)
    gp = mocker.patch("gitlabemu.runner.get_pipeline", return_value=(gl, FakeProject(), pipe))
    run(["--download", "emulator-linux-test", "--from", "gitlab.none/group/project/1234"])
    _, stderr = capsys.readouterr()

    assert gp.called
    assert pipe.jobs.list.called
    assert zipfile.called
