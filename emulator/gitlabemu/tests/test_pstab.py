"""Tests for pstab.py"""
import os

import pytest

from ..pstab import Base, Proc, Powershell


@pytest.mark.usefixtures("linux_only")
def test_procfs():
    pids = Proc().get_pids()
    assert len(pids) > 0
    assert os.getpid() in pids


@pytest.mark.usefixtures("posix_only")
def test_ps():
    pids = Base().get_pids()
    assert len(pids) > 0
    assert os.getpid() in pids


@pytest.mark.usefixtures("windows_only")
def test_powershell():
    pids = Powershell().get_pids()
    assert len(pids) > 0
    assert os.getpid() in pids
