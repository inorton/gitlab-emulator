"""Tests for configtool and userconfigdata"""
import os
import uuid

import pytest
from .. import configtool


@pytest.fixture(scope="function")
def custom_config():
    os.environ["GLE_CONFIG"] = "/tmp/gle-tests/test-gle-config.yml"
    if os.path.exists(os.environ["GLE_CONFIG"]):
        os.unlink(os.environ["GLE_CONFIG"])
    return os.environ["GLE_CONFIG"]


@pytest.mark.usefixtures("linux_only")
def test_help_shows_commands(capfd: pytest.CaptureFixture):
    with pytest.raises(SystemExit):
        configtool.main(["--help"])
    stdout, stderr = capfd.readouterr()
    assert "{context,vars,volumes,windows-shell}" in stdout


def test_context(custom_config: str, capfd: pytest.CaptureFixture):
    """Test we can create, see and use contexts"""
    assert not os.path.exists(custom_config)
    configtool.main(["context"])
    stdout, stderr = capfd.readouterr()
    trimmed = stdout.strip()
    assert "* emulator" == trimmed

    # make a context
    configtool.main(["context", "bob"])
    stdout, stderr = capfd.readouterr()
    assert "notice: gle context set to bob" in stderr
    assert os.path.exists(custom_config)
    configtool.main(["context"])
    stdout, stderr = capfd.readouterr()
    assert "  emulator" in stdout
    assert "* bob" in stdout

    # delete a context
    configtool.main(["context", "bob", "--remove"])
    configtool.main(["context"])
    stdout, stderr = capfd.readouterr()
    assert "* emulator" in stdout
    assert "bob" not in stdout


def test_vars(custom_config: str, capfd: pytest.CaptureFixture):
    """Test we can set the 3 types of variables"""
    # check file doesn't exist
    assert not os.path.exists(custom_config)

    # check nothing is printed
    configtool.main(["vars"])
    configtool.main(["vars", "--local"])
    configtool.main(["vars", "--docker"])

    stdout, stderr = capfd.readouterr()
    assert stdout == ""
    # check file doesn't exist (no changes have been made)
    assert not os.path.exists(custom_config)

    # check unset vars
    configtool.main(["vars", "FOO"])
    stdout, stderr = capfd.readouterr()
    assert "FOO is not set" in stdout

    # set some vars
    configtool.main(["vars", "FOO=red"])
    stdout, stderr = capfd.readouterr()
    assert "notice: Setting FOO" in stderr
    # config should now exist
    assert os.path.exists(custom_config)

    # set empty warning
    # unset forst
    configtool.main(["vars", "BAR="])
    stdout, stderr = capfd.readouterr()
    assert "warning: BAR is not set" in stderr
    configtool.main(["vars", "BAR=''"])
    stdout, stderr = capfd.readouterr()
    assert "notice: Setting BAR" in stderr

    # set variables for local jobs and docker jobs
    for custom in ["local", "docker"]:
        configtool.main(["vars", f"JOBTYPE={custom}", f"--{custom}"])
        stdout, stderr = capfd.readouterr()
        assert "notice: Setting JOBTYPE" in stderr
        configtool.main(["vars", "JOBTYPE", f"--{custom}"])
        stdout, stderr = capfd.readouterr()
        assert f"JOBTYPE={custom}" in stdout
        configtool.main(["vars", f"--{custom}"])
        stdout, stderr = capfd.readouterr()
        assert f"JOBTYPE={custom}" in stdout

        # unset
        configtool.main(["vars", f"--{custom}", "JOBTYPE="])
        stdout, stderr = capfd.readouterr()
        assert "notice: Unsetting JOBTYPE" in stderr
        configtool.main(["vars", f"--{custom}"])
        stdout, stderr = capfd.readouterr()
        assert "JOBTYPE" not in stdout


def test_volumes(custom_config: str, capfd: pytest.CaptureFixture, tmp_path):
    """Test volume management"""
    assert not os.path.exists(custom_config)
    configtool.main(["volumes"])
    stdout, stderr = capfd.readouterr()
    assert stdout == ""
    # check file doesn't exist (no changes have been made)
    assert not os.path.exists(custom_config)

    configtool.main(["volumes"])
    stdout, stderr = capfd.readouterr()
    assert stdout == ""

    # make a volume
    host_volume = f"/{uuid.uuid4()}"
    configtool.main(["volumes", "--add", f"{host_volume}:/mnt/foo:ro"])
    assert os.path.exists(custom_config)
    configtool.main(["volumes"])
    stdout, stderr = capfd.readouterr()
    assert f"{host_volume}:/mnt/foo:ro" in stdout
    # remove it
    configtool.main(["volumes", "--remove", "/mnt/foo"])
    configtool.main(["volumes"])
    stdout, stderr = capfd.readouterr()
    assert "/mnt/foo" not in stdout

    # make a windows one
    configtool.main(["volumes", "--add", f"c:\\test:c:\\stuff"])
    stdout, stderr = capfd.readouterr()
    assert "c:\\test:c:\\stuff:rw" in stdout


def test_windows_shell(custom_config: str, capfd: pytest.CaptureFixture):
    assert not os.path.exists(custom_config)
    configtool.main(["windows-shell"])
    stdout, stderr = capfd.readouterr()
    assert "Windows shell is powershell" in stdout

    configtool.main(["windows-shell", "--cmd"])
    stdout, stderr = capfd.readouterr()
    assert "Windows shell is cmd" in stdout

    configtool.main(["windows-shell", "--powershell"])
    stdout, stderr = capfd.readouterr()
    assert "Windows shell is powershell" in stdout

    with pytest.raises(SystemExit) as err:
        configtool.main(["windows-shell", "--cmd", "--powershell"])
    assert err.value.code != 0


def test_print_sensitive(capfd: pytest.CaptureFixture):
    configtool.print_sensitive_vars(
        {
            "HELLO": "world",
            "MY_PASSWORD": "moosepass"
         }
    )
    stdout, stderr = capfd.readouterr()
    assert "moosepass" not in stdout
    assert "HELLO=world" in stdout
    assert "MY_PASSWORD=**" in stdout


def test_usage(capfd: pytest.CaptureFixture):
    configtool.main([])
    stdout, stderr = capfd.readouterr()
    assert "usage:" in stdout
