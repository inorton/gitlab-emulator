"""Cross platform pure python process inspection"""
import platform
from typing import List
import os
import subprocess


class Base:

    cmdline = ["ps", "ax"]

    def get_process_list(self) -> List[str]:
        stdout = subprocess.check_output(self.cmdline,
                                         encoding="utf-8",
                                         stderr=subprocess.DEVNULL)
        lines = [line for line in stdout.splitlines(keepends=False)]
        return lines

    def get_pids(self) -> List[int]:
        pids = []
        for line in self.get_process_list():
            content = line.strip()
            if content:
                words = content.split()
                if words:
                    try:
                        pids.append(int(words[0]))
                    except ValueError:
                        pass
        return pids


class Proc(Base):
    """Inspect processes using /proc"""

    def get_pids(self) -> List[int]:
        files = os.listdir("/proc")
        pids = []
        for item in files:
            try:
                pids.append(int(item))
            except ValueError:
                pass
        return pids


class Powershell(Base):
    """Windows powershell"""
    cmdline = ["powershell", "-Command", "Get-Process"]  # pragma: linux no cover


def get_pids() -> List[int]:
    if platform.system() == "Windows":
        p = Powershell()
    elif os.path.isdir("/proc"):
        p = Proc()
    else:
        p = Base()

    return p.get_pids()
