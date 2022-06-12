import os
from typing import Optional
import psutil
import uuid

PID = os.getpid()


def generate_resource_name(kind: Optional[str] = None) -> str:
    """Generate a name related to this instance of gitlab-emulator"""
    if not kind:
        kind = "docker"
    rnd = str(uuid.uuid4())[0:7]
    return f"gle-{kind}-{PID}-{rnd}"


def is_gle_resource(name: str) -> Optional[int]:
    """Return the PID if this resource was created by gitlab emulator"""
    if name:
        parts = name.split("-")
        if len(parts) == 4:
            prefix = parts[0]
            if prefix == "gle":
                pid = int(parts[2])
                return pid
    return None


def resource_owner_alive(name: str) -> bool:
    """Return True if the owner of this resource is still alive"""
    pid = is_gle_resource(name)
    if pid is not None:
        return psutil.pid_exists(pid)
    return False
