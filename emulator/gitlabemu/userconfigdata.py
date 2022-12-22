import abc
import os.path
from typing import Optional, Dict, List
from yaml import safe_dump, safe_load
from .helpers import plausible_docker_volume, DockerVolume
from .logmsg import fatal


DEFAULT_CONTEXT = "emulator"
FORBIDDEN_CONTEXT_NAMES = [
    "current_context",
    # reserved
    "version",
]
DEFAULT_GITLAB_VERSION = "15.7"


class ToYaml(abc.ABC):
    @abc.abstractmethod
    def to_dict(self) -> dict:
        pass

    @abc.abstractmethod
    def populate(self, data: dict) -> None:
        pass

    def setattrs_from_dict(self, data: dict, *props) -> None:
        for prop in props:
            if prop in data:
                setattr(self, prop, data.get(prop))


class GitlabServer(ToYaml):
    def __init__(self):
        self.name = None
        self.server = None
        self.token = None
        self.tls_verify = True

    def to_dict(self) -> dict:
        res = {
            "name": self.name,
            "server": self.server,
            "token": self.token,
        }
        if not self.tls_verify:
            res["tls_verify"] = False
        return res

    def populate(self, data) -> None:
        self.setattrs_from_dict(data, "name", "server", "token", "tls_verify")


class GitlabConfiguration(ToYaml):
    def __init__(self):
        self.version = DEFAULT_GITLAB_VERSION
        self.servers = []

    def add(self, name: str, url: str, token: str, tls_verify: bool):
        server = GitlabServer()
        server.tls_verify = tls_verify
        server.token = token
        server.server = url
        server.name = name
        self.servers.append(server)
        return server

    def to_dict(self) -> dict:
        res = {}
        if self.version:
            res["version"] = str(self.version)
        res["servers"] = [x.to_dict() for x in self.servers]
        return dict(res)

    def populate(self, data) -> None:
        self.version = str(data.get("version", DEFAULT_GITLAB_VERSION))
        for item in data.get("servers", []):
            server = GitlabServer()
            server.populate(item)
            self.servers.append(server)


class VariablesConfiguration(ToYaml):
    def __init__(self):
        self.variables = dict()

    def to_dict(self) -> dict:
        res = dict()
        if self.variables:
            res["variables"] = dict(self.variables)
        return res

    def populate(self, data: dict) -> None:
        self.setattrs_from_dict(data, "variables")


class DockerConfiguration(VariablesConfiguration):
    def __init__(self):
        super(DockerConfiguration, self).__init__()
        self.volumes = []

    def runtime_volumes(self) -> List[str]:
        volumes = os.getenv("GLE_DOCKER_VOLUMES", None)
        if volumes is not None:
            volumes = volumes.split(",")
        else:
            volumes = self.volumes
        return list(volumes)

    def add_volume(self, text: str) -> DockerVolume:
        """Add a docker volume mount point"""
        volume = plausible_docker_volume(text)
        if volume:
            # remove this mount point if it is already used
            self.remove_volume(volume.mount)
            self.volumes.append(str(volume))
        return volume

    def remove_volume(self, mount: str):
        """Remove a docker volume mount point"""
        keep_volumes = []
        for item in self.volumes:
            volume = plausible_docker_volume(item)
            if volume.mount == mount:
                continue
            keep_volumes.append(str(volume))
        self.volumes = list(set(keep_volumes))

    def to_dict(self) -> dict:
        self.validate()
        res = super(DockerConfiguration, self).to_dict()
        if self.volumes:
            res["volumes"] = list(self.volumes)
        return res

    def populate(self, data: dict) -> None:
        super(DockerConfiguration, self).populate(data)
        self.setattrs_from_dict(data, "volumes")
        # validate the volumes
        self.validate()

    def validate(self):
        for volume in self.volumes:
            if plausible_docker_volume(volume) is None:
                fatal(f"Unable to parse docker volume string '{volume}'")


class WindowsConfiguration(ToYaml):
    def __init__(self):
        self.cmd = False

    def to_dict(self) -> dict:
        res = {}
        if self.cmd:
            res["cmd"] = True
        return res

    def populate(self, data: dict) -> None:
        self.setattrs_from_dict(data, "cmd")


class UserContext(VariablesConfiguration):
    def __init__(self):
        super(UserContext, self).__init__()
        self.windows = WindowsConfiguration()
        self.docker = DockerConfiguration()
        self.local = VariablesConfiguration()
        self.gitlab = GitlabConfiguration()
        self.filename: Optional[str] = None

    def to_dict(self) -> dict:
        res = super(UserContext, self).to_dict()
        res.update({
            "gitlab": self.gitlab.to_dict(),
            "docker": self.docker.to_dict(),
            "local": self.local.to_dict(),
        })
        windows = self.windows.to_dict()
        if len(windows):
            res["windows"] = windows
        return res
                
    def populate(self, data: dict) -> None:
        super(UserContext, self).populate(data)
        for name in ["windows", "docker", "gitlab", "local"]:
            element = getattr(self, name)
            element.populate(data.get(name, {}))
        

class UserConfigFile(ToYaml):
    def __init__(self):
        self.current_context: Optional[str] = None
        self.contexts: Dict[str, UserContext] = {}
        self.filename: Optional[str] = None

    def load(self, filename: str) -> None:
        self.filename = os.path.abspath(filename)
        data = {}
        if os.path.exists(filename):
            with open(self.filename, "r") as yfile:
                data: dict = safe_load(yfile)
        if data is None:
            # the file was empty?
            data = {}
        self.populate(data)

    def populate(self, data: dict) -> None:
        self.current_context = data.get("current_context", DEFAULT_CONTEXT)
        for name in data.keys():
            if name not in FORBIDDEN_CONTEXT_NAMES:
                self.contexts[name] = UserContext()
                self.contexts[name].populate(data.get(name, {}))

        if self.current_context not in self.contexts:
            self.contexts[self.current_context] = UserContext()

    def to_dict(self) -> dict:
        res = {
            "current_context": self.current_context,
        }
        for item in self.contexts:
            res[item] = self.contexts[item].to_dict()
        return res

    def save(self, filename: Optional[str] = None):
        if filename is None:
            filename = self.filename

        if filename and os.path.basename(filename):
            self.filename = os.path.abspath(filename)
            filename = self.filename
        else:
            filename = None

        if filename:
            folder = os.path.dirname(os.path.abspath(filename))
            if not os.path.exists(folder):
                os.makedirs(folder)

            with open(filename, "w") as yfile:
                safe_dump(self.to_dict(), yfile,
                          width=120,
                          indent=2,
                          default_flow_style=False)
        return filename
