import abc
import os.path
from typing import Optional, Dict, List, cast
from yaml import safe_dump, safe_load

from .helpers import plausible_docker_volume, DockerVolume, is_windows, has_docker, notice
from .logmsg import fatal, debug

DEFAULT_CONTEXT = "emulator"
FORBIDDEN_CONTEXT_NAMES = [
    "current_context",
    # reserved
    "version",
]
DEFAULT_GITLAB_VERSION = "15.7"
DEFAULT_DOCKER_CLI = "docker"

EXECUTOR_SHELL = "shell"
EXECUTOR_DOCKER = "docker"
EXECUTOR_DOCKER_WINDOWS = "docker-windows"
RUNNER_EXECUTOR_TYPES = [EXECUTOR_SHELL, EXECUTOR_DOCKER, EXECUTOR_DOCKER_WINDOWS]

SHELL_SH = "sh"
SHELL_BASH = "bash"
SHELL_POWERSHELL = "powershell"
RUNNER_SHELL_SHELLS = [SHELL_SH, SHELL_BASH, SHELL_POWERSHELL]


class ToYaml(abc.ABC):

    @property
    def serialize_empty(self) -> bool:
        return False

    def to_dict(self) -> dict:
        res = {}
        for name in self.yaml_keys:
            assert hasattr(self, name), name
            value = getattr(self, name)
            # omit empty lists, dicts and None values
            if isinstance(value, ToYaml):
                dict_value = value.to_dict()
                if dict_value or value.serialize_empty:
                    res[name] = dict_value
            elif isinstance(value, dict):
                if len(value):
                    dictvalue = {}
                    for item_key, item_value in value.items():
                        if isinstance(item_value, ToYaml):
                            dictvalue[item_key] = item_value.to_dict()
                        else:
                            dictvalue[item_key] = item_value
                    res[name] = dictvalue
            elif isinstance(value, list):
                if len(value):
                    listvalue = []
                    for item_value in value:
                        if isinstance(item_value, ToYaml):
                            listvalue.append(item_value.to_dict())
                        else:
                            listvalue.append(item_value)
                    res[name] = listvalue
            elif value is not None:
                res[name] = value
        return res

    @property
    def yaml_keys(self) -> List[str]:
        return []

    def populate(self, data: dict):
        for name, value in data.items():
            if name in self.yaml_keys:
                if hasattr(self, name):
                    setattr(self, name, value)
        return self

    def setattrs_from_dict(self, data: dict, *props) -> None:
        for prop in props:
            if prop in data:
                if hasattr(self, prop):
                    setattr(self, prop, data.get(prop))


class GitlabServer(ToYaml):
    def __init__(self):
        self.name = None
        self.server = None
        self.token = None
        self.tls_verify = True

    @property
    def yaml_keys(self) -> List[str]:
        return ["name", "server", "token", "tls_verify"]

    def populate(self, data):
        self.setattrs_from_dict(data, *self.yaml_keys)
        return self


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

    @property
    def yaml_keys(self) -> List[str]:
        return ["version", "servers"]

    def populate(self, data):
        self.version = str(data.get("version", DEFAULT_GITLAB_VERSION))
        for item in data.get("servers", []):
            server = GitlabServer()
            server.populate(item)
            self.servers.append(server)
        return self


class VariablesConfiguration(ToYaml):
    def __init__(self):
        self.variables = dict()

    @property
    def yaml_keys(self) -> List[str]:
        return ["variables"]

    def populate(self, data: dict):
        self.setattrs_from_dict(data, "variables")
        return self


class VolumesMixin:
    def runtime_volumes(self) -> List[str]:
        volumes = os.getenv("GLE_DOCKER_VOLUMES", None)
        if volumes is not None:
            volumes = volumes.split(",")
        else:
            volumes = getattr(self, "volumes")
        return list(volumes)

    def add_volume(self, text: str) -> DockerVolume:
        """Add a docker volume mount point"""
        volume = plausible_docker_volume(text)
        if volume:
            # remove this mount point if it is already used
            self.remove_volume(volume.mount)
            getattr(self, "volumes").append(str(volume))
        return volume

    def remove_volume(self, mount: str):
        """Remove a docker volume mount point"""
        possible = plausible_docker_volume(mount)
        if possible:
            mount = possible.mount
        keep_volumes = []
        volumes = getattr(self, "volumes")
        for item in volumes:
            volume = plausible_docker_volume(item)
            if volume.mount == mount:
                continue
            keep_volumes.append(str(volume))
        setattr(self, "volumes", list(set(keep_volumes)))


class DockerConfiguration(VariablesConfiguration, VolumesMixin):
    def __init__(self):
        self.privileged = True
        self.docker_cli = DEFAULT_DOCKER_CLI
        super(DockerConfiguration, self).__init__()
        self.volumes = []

    @property
    def yaml_keys(self) -> List[str]:
        return super().yaml_keys + ["volumes", "privileged", "docker_cli"]

    def populate(self, data: dict):
        super(DockerConfiguration, self).populate(data)
        self.setattrs_from_dict(data, "volumes", "privileged", "docker_cli")
        # validate the volumes
        self.validate()
        return self

    def validate(self):
        for volume in self.volumes:
            if plausible_docker_volume(volume) is None:
                fatal(f"Unable to parse docker volume string '{volume}'")


class WindowsConfiguration(ToYaml):
    def __init__(self):
        self.cmd = False

    @property
    def yaml_keys(self) -> List[str]:
        return ["cmd"]

    def populate(self, data: dict):
        self.setattrs_from_dict(data, "cmd")
        return self


class UserContext(VariablesConfiguration):
    def __init__(self):
        super(UserContext, self).__init__()
        self.windows = WindowsConfiguration()
        self.docker = DockerConfiguration()
        self.local = VariablesConfiguration()
        self.gitlab = GitlabConfiguration()
        self.filename: Optional[str] = None
        self.runners: List[GleRunnerConfig] = []

    def remove_runner(self, name: str):
        self.runners = [x for x in self.runners if x.name != name]

    def save_runner(self, runner: "GleRunnerConfig"):
        exists = self.get_runner(runner.name)
        if exists:
            self.remove_runner(runner.name)
        self.runners.append(runner)

    def find_runner(self,
                    image: bool = False,
                    tags: Optional[List[str]] = None,
                    ) -> Optional["GleRunnerConfig"]:
        """Find a runner configuration for the given image+tag combo"""
        if tags is None:
            tags = []

        tagset = set(tags)
        debug(f"find runner for image={image}, tags={tags}")
        for runner in self.runners + self.builtin_runners():
            if image and runner.executor not in [EXECUTOR_DOCKER, EXECUTOR_DOCKER_WINDOWS]:
                continue
            if not image:
                if runner.executor in [EXECUTOR_DOCKER, EXECUTOR_DOCKER_WINDOWS]:
                    continue
            debug(f"considering runner {runner}")
            if len(tagset) == 0:
                if runner.run_untagged:
                    debug(f"matching {runner} - allow untagged")
                    return runner
            else:
                runner_tagset = set(runner.tags)
                if tagset.issubset(runner_tagset):
                    debug(f"matching {runner} - tags {tagset}")
                    return runner

        # nothing matched, return the defaults but warn
        if image:
            runner = self.get_runner("default-docker", builtins=True)
        else:
            runner = self.get_runner("default-shell", builtins=True)
        debug(f"matched default {runner}")
        return runner

    def get_runner(self, name: str, builtins=False) -> Optional["GleRunnerConfig"]:
        runners = list(self.runners)
        if builtins:
            runners.extend(self.builtin_runners())
        for runner in runners:
            if runner.name == name:
                return runner
        return None

    def can_add_name(self, name: str) -> bool:
        return self.get_runner(name, builtins=True) is None

    def builtin_runners(self) -> List["GleRunnerConfig"]:
        ret = []
        if has_docker():
            builtin_docker = GleRunnerConfig()
            builtin_docker.name = "default-docker"
            builtin_docker.is_builtin = True
            builtin_docker.executor = "docker"
            builtin_docker.docker = DockerExecutorConfig()
            builtin_docker.docker.privileged = self.docker.privileged
            builtin_docker.run_untagged = True
            builtin_docker.docker.volumes = list(self.docker.runtime_volumes())
            builtin_docker.environment = dict(self.docker.variables)
            ret.append(builtin_docker)
        builtin_shell = GleRunnerConfig()
        builtin_shell.executor = "shell"
        builtin_shell.name = "default-shell"
        builtin_shell.shell = SHELL_BASH
        if is_windows():  # pragma: cover if windows
            builtin_shell.shell = SHELL_POWERSHELL
        ret.append(builtin_shell)
        return ret

    @property
    def yaml_keys(self) -> List[str]:
        return super().yaml_keys + ["gitlab", "docker", "local", "windows", "runners"]
                
    def populate(self, data: dict) -> None:
        super(UserContext, self).populate(data)
        for name in ["windows", "docker", "gitlab", "local"]:
            element = getattr(self, name)
            element.populate(data.get(name, {}))
        runners = data.get("runners", [])
        self.runners = [GleRunnerConfig().populate(x) for x in runners]


class UserConfigFile(ToYaml):
    def __init__(self):
        self.current_context: Optional[str] = None
        self.contexts: Dict[str, UserContext] = {}
        self.filename: Optional[str] = None

    def to_dict(self) -> dict:
        res = {
            "current_context": self.current_context
        }
        for name, ctx in self.contexts.items():
            res[name] = ctx.to_dict()
        return res

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

    def populate(self, data: dict):
        self.current_context = data.get("current_context", DEFAULT_CONTEXT)
        for name in data.keys():
            if name not in FORBIDDEN_CONTEXT_NAMES:
                self.contexts[name] = UserContext()
                self.contexts[name].populate(data.get(name, {}))

        if self.current_context not in self.contexts:
            self.contexts[self.current_context] = UserContext()
        return self

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
                data = self.to_dict()
                safe_dump(data, yfile,
                          width=120,
                          indent=2,
                          default_flow_style=False)
        return filename


class DockerExecutorConfig(ToYaml, VolumesMixin):

    def __init__(self):
        self.privileged = False
        self.image: str = "alpine:latest"
        self.volumes: List[str] = []
        self.cap_add: str = ""
        self.mac_address: str = ""
        self.docker_cli = DEFAULT_DOCKER_CLI

    @property
    def yaml_keys(self) -> List[str]:
        return ["privileged",
                "image",
                "volumes",
                "cap_add",
                "mac_address",
                "docker_cli",
                ]


class GleRunnerConfig(ToYaml):

    def __init__(self):
        self.name: str = "local"
        self.tags: List[str] = []
        self.run_untagged = False
        self.executor: str = "docker"
        self.shell: str = SHELL_POWERSHELL if is_windows() else SHELL_BASH
        self.docker: Optional[DockerExecutorConfig] = None
        self.pre_build_script: str = ""
        self.environment: Dict[str, str] = {}
        self.is_builtin: bool = False

    def __str__(self):
        return f"{self.executor}-runner {self.name}"

    @property
    def yaml_keys(self) -> List[str]:
        keys = ["name", "tags", "run_untagged", "executor", "environment", "shell", "pre_build_script"]
        if self.executor == "docker":
            keys.append("docker")
        return keys

    def populate(self, data: dict):
        super().populate(data)
        if self.docker is not None:
            self.docker = DockerExecutorConfig().populate(cast(dict, self.docker))
        return self
