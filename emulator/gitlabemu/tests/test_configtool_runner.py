"""Tests for gle-config runner"""
import pytest
from _pytest.capture import CaptureFixture
from ..configtool import main
from ..helpers import is_windows
from ..userconfig import get_user_config_context

@pytest.mark.usefixtures("custom_config")
def test_list_runners(capfd: CaptureFixture):
    # no args defaults to list
    main(["runner"])
    stdout, stderr = capfd.readouterr()
    assert "name" in stderr
    assert "--------" in stderr
    assert "default-shell" in stdout


@pytest.mark.usefixtures("custom_config")
def test_add_edit_runners(capfd: CaptureFixture):
    ctx = get_user_config_context()
    assert len(ctx.runners) == 0
    main(["runner", "add", "bob", "--tags", "one,two"])
    stdout, stderr = capfd.readouterr()
    assert "saved runner bob :-" in stderr
    assert "name: bob" in stdout

    ctx = get_user_config_context()
    assert len(ctx.runners) == 1
    bob = ctx.get_runner("bob")
    assert bob
    assert bob.tags == ["one", "two"]
    assert bob.executor == "docker"
    if is_windows():
        assert bob.shell == "powershell"
    else:
        assert bob.shell == "bash"
    assert bob.run_untagged is False
    assert bob.docker.privileged is False
    assert len(bob.docker.volumes) == 0
    capfd.readouterr()
    # edit bob
    main(["runner", "edit", "bob", "--privileged", "true", "--shell", "sh"])
    stdout, stderr = capfd.readouterr()
    assert "privileged: true" in stdout
    ctx = get_user_config_context()
    bob = ctx.get_runner("bob")
    assert bob.docker.privileged
    assert bob.shell == "sh"

    # set untagged
    main(["runner", "edit", "bob", "--untagged", "true"])
    stdout, stderr = capfd.readouterr()
    assert "run_untagged: true" in stdout

    # unset untagged
    main(["runner", "edit", "bob", "--untagged", "false"])
    stdout, stderr = capfd.readouterr()
    assert "run_untagged: true" not in stdout

    # show bob
    main(["runner", "edit", "bob"])
    stdout, stderr = capfd.readouterr()
    assert "privileged: true" in stdout
    assert "shell: sh" in stdout

    # add volumes
    main(["runner", "edit", "bob", "--add-volume", "/tmp:/tmp/host"])
    stdout, stderr = capfd.readouterr()
    assert "- /tmp:/tmp/host:rw" in stdout
    ctx = get_user_config_context()
    bob = ctx.get_runner("bob")
    assert bob.docker.volumes == ["/tmp:/tmp/host:rw"]

    # add another volume
    main(["runner", "edit", "bob", "--add-volume", "/baa:/tmp/host2:ro"])
    stdout, stderr = capfd.readouterr()
    assert "- /tmp:/tmp/host:rw" in stdout
    assert "- /baa:/tmp/host2:ro" in stdout
    ctx = get_user_config_context()
    bob = ctx.get_runner("bob")
    assert bob.docker.volumes == ["/tmp:/tmp/host:rw",
                                  "/baa:/tmp/host2:ro"]
    # remove a volume
    main(["runner", "edit", "bob", "--remove-volume", "/baa:/tmp/host2:ro"])
    stdout, stderr = capfd.readouterr()
    assert "/tmp/host2" not in stdout

    ctx = get_user_config_context()
    # there should only be 1 extra runner now
    builtin_runners = ctx.builtin_runners()
    assert len(builtin_runners) > 0
    assert len(builtin_runners) < 3
    runners = ctx.runners
    assert len(runners) == 1

    # try to make without a name
    with pytest.raises(SystemExit):
        main(["runner", "add"])
    stdout, stderr = capfd.readouterr()
    assert "missing required runner name" in stderr

    # try to make another bob
    with pytest.raises(SystemExit):
        main(["runner", "add", "bob"])
    stdout, stderr = capfd.readouterr()
    assert "A runner named bob already exists" in stderr

    # try to make a built-in
    with pytest.raises(SystemExit):
        main(["runner", "add", "default-shell"])
    stdout, stderr = capfd.readouterr()
    assert "Cannot add a new runner named default-shell" in stderr

    # finally, delete bob
    main(["runner", "rm", "bob"])
    stdout, stderr = capfd.readouterr()
    assert "removed runner bob" in stderr
    ctx = get_user_config_context()
    bob = ctx.get_runner("bob")
    assert bob is None

    # try to view the now deleted bob
    with pytest.raises(SystemExit):
        main(["runner", "edit", "bob"])
    stdout, stderr = capfd.readouterr()
    assert "No such runner bob" in stderr

@pytest.mark.usefixtures("custom_config")
def test_runner_set_unset_env():
    main(["runner", "add", "fred"])
    ctx = get_user_config_context()
    fred = ctx.get_runner("fred")
    assert len(fred.environment) == 0

    # set some envs
    for var in ["COLOR=red", "SIZE=little"]:
        main(["runner", "edit", "fred", "--set", var])

    ctx = get_user_config_context()
    fred = ctx.get_runner("fred")
    assert len(fred.environment) == 2
    assert fred.environment["COLOR"] == "red"
    assert fred.environment["SIZE"] == "little"

    main(["runner", "edit", "fred", "--unset", "SIZE"])
    ctx = get_user_config_context()
    fred = ctx.get_runner("fred")
    assert len(fred.environment) == 1
    assert fred.environment["COLOR"] == "red"

