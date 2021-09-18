"""
Test functions of the runner without a server
"""
import os
import stat
from contextlib import contextmanager

from GitlabPyRunner.runner import Runner
from GitlabPyRunner.executor import archive
from GitlabPyRunner.common import iswindows


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
    if not iswindows():
        stats = os.stat(unpacked)
        assert stats
        mode = stat.S_IMODE(stats.st_mode)
        assert mode & stat.S_IXUSR  # owner has execute

    captured = capsys.readouterr()

    assert captured
    assert "Unpacking artifacts into {}..".format(tmpdir.strpath) in captured.out
