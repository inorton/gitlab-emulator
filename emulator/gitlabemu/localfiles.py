"""
Utils for local file housekeeping
"""
import os
from .helpers import has_docker, is_linux
from .docker import DockerTool


def restore_path_ownership(path):
    path = os.path.abspath(path)
    chowner = os.path.abspath(os.path.join(os.path.dirname(__file__), "chown.py"))
    if is_linux():  # pragma: cover if not windows
        if os.getuid() != 0:
            if has_docker():
                from .resnamer import generate_resource_name
                dt = DockerTool()
                dt.name = generate_resource_name("chowner")
                dt.image = "python:3.9-alpine3.14"
                dt.privileged = False
                dt.add_volume(path, path)
                dt.add_volume(chowner, "/chown.py")

                if not dt.image_present:
                    dt.pull()
                dt.run(detached=False, args=["python3", "/chown.py", str(os.getuid()), str(os.getgid()), str(path)])
