"""Extra tests for userconfigdata.py"""
import os
from pathlib import Path

import pytest

from ..userconfigdata import UserConfigFile, DockerConfiguration


def test_empty_file(tmp_path: Path):
    empty = tmp_path / "empty.yml"
    empty.write_text("", encoding="utf-8")

    cfg = UserConfigFile()
    cfg.load(empty)

    assert cfg.filename == str(empty)
    assert cfg.current_context == "emulator"
    assert len(cfg.contexts) == 1


def test_save_filename(tmp_path: Path):
    cfg = UserConfigFile()
    assert not cfg.filename
    cfg.filename = str(tmp_path / "folder" / "file.yml")
    assert not os.path.exists(cfg.filename)
    saved = cfg.save()
    assert saved == cfg.filename
    assert os.path.exists(cfg.filename)

    copyfile = str(tmp_path / "somewhere" / "copy.yml")
    assert not os.path.exists(copyfile)
    saved = cfg.save(copyfile)
    assert saved == copyfile
    assert os.path.exists(copyfile)

    cfg.filename = None
    saved = cfg.save()
    assert not saved


def test_volume_validation():
    docker = DockerConfiguration()
    docker.volumes = [
        "/foo/bar:/moo/mar"
    ]
    docker.validate()

    # add a bad one as though someone has edited the file by hand
    docker.volumes.append("/nothing")
    with pytest.raises(SystemExit):
        docker.validate()


def test_volume_remove_one():
    docker = DockerConfiguration()
    docker.volumes = [
        "/here:/there",
        "/big:/small",
        "/stuff:/and/nonsense",
    ]
    docker.remove_volume("/small")
    docker.validate()
    assert len(docker.volumes) == 2
