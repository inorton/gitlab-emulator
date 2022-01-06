"""
Utils for local file housekeeping
"""
import os
from .helpers import is_windows
from .docker import DockerTool, has_docker


def restore_path_ownership(path):
    path = os.path.abspath(path)
    chowner = os.path.abspath(os.path.join(os.path.dirname(__file__), "chown.py"))
    if not is_windows():
        if has_docker():
            dt = DockerTool()
            dt.name = f"gitlabemu-chowner-{os.getpid()}"
            dt.image = "python:3.8-slim"
            dt.add_volume(path, path)
            dt.entrypoint = ["/bin/sh"]
            dt.pull()
            dt.run()
            try:
                dt.add_file(chowner, "/tmp")
                dt.check_call(path, ["python", "/tmp/chown.py", str(os.getuid()), str(os.getgid())])
            finally:
                dt.kill()

