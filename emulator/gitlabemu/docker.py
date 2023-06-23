import os
import subprocess
import sys
import tempfile
import threading
import time
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional, List, Any
from .logmsg import warning, info, fatal
from .jobs import Job, make_script
from .helpers import communicate as comm, is_windows
from .userconfig import get_user_config_context
from .errors import DockerExecError, GitlabEmulatorError
from .userconfigdata import GleRunnerConfig
from .variables import expand_variable

PULL_POLICY_ALWAYS = "always"
PULL_POLICY_IF_NOT_PRESENT = "if-not-present"
PULL_POLICY_NEVER = "never"


class DockerToolError(GitlabEmulatorError):
    """An error using docker"""
    def __init__(self, msg: str):
        self.message = msg


class DockerToolFailed(DockerToolError):
    """Running docker returned an error"""
    def __init__(self, msg: str, stdout: str, stderr: str):
        super().__init__(msg)
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        return f"docker error: {self.message}\nstderr: {self.stderr}\nstdout:{self.stdout}"


class DockerTool(object):
    """
    Control docker containers
    """
    def __init__(self, retries: Optional[int] = 5):
        self.retries = retries
        self.container: Optional[Any] = None
        self.image = None
        self.env = {}
        self.volumes = []
        self.name = None
        self.privileged = False
        self.entrypoint = None
        self.pulled = None
        self._pull_policy = PULL_POLICY_ALWAYS
        self.network = None
        self._client = None
        self._is_hyerv = None
        self.tool = "docker"

    @property
    def containers(self) -> List[str]:
        try:
            output = self.docker_call("container", "ps", "-q").stdout.strip()
            return output.splitlines(keepends=False)
        except DockerToolError:
            return []

    def container_name(self, containerid: str) -> str:
        output = self.docker_call("container", "inspect", containerid).stdout.strip()
        data = json.loads(output)[0]
        return data["Name"][1:]

    def docker_call(self, *args, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Run the docker command line tool"""
        basic_args = [self.tool] + list(args[:1])
        cmdline = [self.tool] + [str(x) for x in args]
        if cwd is None:
            cwd = Path.cwd()
        try:
            return subprocess.run(cmdline,
                                  cwd=str(cwd.absolute()),
                                  encoding="utf-8",
                                  capture_output=True, check=True)
        except subprocess.CalledProcessError as cpe:
            raise DockerToolFailed(f"{basic_args} failed", cpe.stdout, cpe.stderr)
        except Exception as err:
            raise DockerToolError(f"could not run {basic_args}, {err}")

    def is_windows_hyperv(self) -> bool:
        if self._is_hyerv is None:
            self._is_hyerv = False
            if is_windows():  # pramga: cover if windows
                output = self.docker_call("info", "-f", "{{.Isolation}}").stdout.strip()
                if output == "hyperv":  # pragma: no cover
                    self._is_hyerv = True
        return self._is_hyerv

    @property
    def pull_policy(self) -> str:
        return self._pull_policy
    
    @pull_policy.setter
    def pull_policy(self, value: str):
        assert value in [PULL_POLICY_ALWAYS, PULL_POLICY_IF_NOT_PRESENT, PULL_POLICY_NEVER]
        self._pull_policy = value

    @property
    def can_pull(self) -> bool:
        return self.pull_policy in [PULL_POLICY_ALWAYS, PULL_POLICY_IF_NOT_PRESENT]

    @property
    def pull_always(self) -> bool:
        return self.pull_policy == PULL_POLICY_ALWAYS

    @property
    def pull_if_not_present(self) -> bool:
        return self.pull_policy == PULL_POLICY_IF_NOT_PRESENT

    def add_volume(self, outside, inside):
        self.volumes.append("{}:{}".format(outside, inside))

    def add_env(self, name, value):
        self.env[name] = value

    @property
    def image_present(self) -> bool:
        try:
            self.docker_call("image", "inspect", self.image)
            return True
        except DockerToolFailed:
            return False

    def inspect(self):
        """
        Inspect the image and return the Config dict
        :return:
        """
        if self.image:
            if not self.image_present:
                if self.can_pull:
                    self.pull()
            try:
                output = self.docker_call("image", "inspect", self.image).stdout
                return json.loads(output)[0]
            except DockerToolError:
                pass
        return None

    def add_file(self, src, dest):
        """
        Copy a file to the container
        :param src:
        :param dest:
        :return:
        """
        assert self.container
        need_start = False
        if self.is_windows_hyperv():  # pragma:  cover if windows
            info(f"Pause hyperv container {self.name} for file copy..")
            self.docker_call("stop", self.name)
            info(f"Paused {self.name}")
            need_start = True

        self.docker_call("cp", src, f"{self.name}:{dest}")

        if need_start:  # pragma:  cover if windows
            info(f"Resume hyperv container {self.name} after file copy..")
            self.docker_call("start", self.name)

    def get_user(self):
        image = self.inspect()
        if image and len(image) > 0:
            return image.get("Config", {}).get("User", None)
        return None

    def pull(self):
        if self.can_pull:
            info("pulling docker image {}".format(self.image))
            sys.stdout.write("Pulling {}...\n".format(self.image))
            sys.stdout.flush()
            try:
                self.docker_call("pull", self.image)
                self.pulled = True
            except DockerToolFailed as err:
                info(f"error pulling image: {err}")
                fatal(f"cannot pull image: {self.image} - image not found")

    def get_envs(self):
        cmdline = []
        for name in self.env:
            value = self.env.get(name)
            if value is not None:
                cmdline.extend(["-e", "{}={}".format(name, value)])
            else:
                cmdline.extend(["-e", name])
        return cmdline

    def run(self):
        priv = self.privileged and not is_windows()
        if self.is_windows_hyperv():  # pragma: cover if windows
            warning("windows hyperv container support is very experimental, YMMV")
        volumes = []
        for volume in self.volumes:
            entry = volume
            if not entry.endswith(":ro") and not entry.endswith(":rw"):
                entry += ":rw"
            volumes.append(entry)
        try:
            image = self.inspect()
            if self.entrypoint == ['']:
                if image.get("Os") == "linux":  # pragma: cover if not windows
                    self.entrypoint = "/bin/sh"
                else:
                    self.entrypoint = None
            info(f"launching image {self.image} as container {self.name} ..")
            cmdline = [
                "run",
                "-d",
                "--name", self.name,
            ]
            if self.entrypoint is not None:
                cmdline.extend(["--entrypoint", str(self.entrypoint)])
            if self.network is not None:
                cmdline.extend(["--network", self.network])
            if priv:
                cmdline.append("--privileged")
            if not self.is_windows_hyperv():
                cmdline.append("--rm")
            for volume in volumes:
                cmdline.extend(["-v", volume])
            for name, value in self.env.items():
                cmdline.extend(["-e", f"{name}={value}"])
            cmdline.extend(["-i", self.image])

            proc = self.docker_call(*cmdline)
            self.container = proc.stdout.strip()
        except DockerToolFailed:  # pragma: no cover
            if not self.image_present:
                fatal(f"Docker image {self.image} does not exist, (pull_policy={self.pull_policy})")
            warning(f"problem running {self.image}")
            raise

    def kill(self):
        if self.container:
            self.docker_call("kill", "-s", "9", self.container)

    def check_call(self, cwd: str, cmd: List[str], stdout=None, stderr=None, capture=False):
        cmdline = [self.tool, "exec", "-w", cwd, self.container] + cmd
        if capture:
            return subprocess.check_output(cmdline, stderr=stderr)
        else:
            return subprocess.check_call(cmdline, stdout=stdout, stderr=stderr)

    def exec(self, cwd: str, shell: List[str], tty=False, user=None, pipe=True):
        cmdline = [self.tool, "exec", "-w", cwd]
        cmdline.extend(self.get_envs())
        if user is not None:
            cmdline.extend(["-u", str(user)])
        if tty:  # pragma: no cover
            cmdline.append("-t")
            pipe = False
        cmdline.extend(["-i", self.container])
        cmdline.extend(shell)

        if pipe:
            proc = subprocess.Popen(cmdline,
                                    shell=False,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            return proc
        else:  # pragma: no cover
            return subprocess.Popen(cmdline,
                                    shell=False)


class DockerJob(Job):
    """
    Run a job inside a docker container
    """
    def __init__(self):
        super(DockerJob, self).__init__()
        self._image = None
        self.services = []
        self.container = None
        self.docker = DockerTool()
        self._force_pull_policy = None
        self._container_lock = threading.Lock()
        self._has_bash = None
        self._shell_uid = 0
        self._shell_gid = 0

    @property
    def shell_is_user(self):
        return super().shell_is_user

    @shell_is_user.setter
    def shell_is_user(self, value: bool):
        self._shell_is_user = value
        if value:
            self._shell_uid = os.getuid()
            self._shell_gid = os.getgid()

    @property
    def docker_image(self) -> str:
        if isinstance(self._image, dict):
            image = self._image.get("name", None)
        else:
            image = self._image
        return expand_variable(self.get_envs(), image)

    @property
    def docker_entrypoint(self) -> Optional[List[str]]:
        custom_entryppoint = None
        if isinstance(self._image, dict):
            custom_entryppoint = self._image.get("entrypoint", None)
        return custom_entryppoint

    @property
    def docker_pull_policy(self) -> Optional[str]:
        policy = self._force_pull_policy
        if policy is None:
            if isinstance(self._image, dict):
                policy = self._image.get("pull_policy", None)
        return policy

    @docker_pull_policy.setter
    def docker_pull_policy(self, value: Optional[str]):
        self._force_pull_policy = value
        self.docker.pull_policy = value

    @property
    def inside_workspace(self) -> str:
        if is_windows():
            import ntpath
            # if the workspace is not on c:, map it to a c: location in the container
            # or if the path is quite long
            if not self.workspace.lower().startswith("c:") or len(self.workspace) > 32:
                basedir = ntpath.basename(self.workspace)
                return f"c:\\b\\{basedir}"[:14]
        else:
            if len(self.workspace) > 80:
                # truncate really long paths even on linux
                return f"/b/{os.path.basename(self.workspace)[:64]}"

        return self.workspace

    def allocate_runner(self):
        if self.runner is None:  # pragma: no cover
            raise GitlabEmulatorError(f"could not find a local docker runner for this job@ {self.name}")
        super().allocate_runner()
        if self.runner and self.runner.docker:
            if self._image is None:
                self._image = self.runner.docker.image
            self.docker.privileged = self.runner.docker.privileged
            if self.runner.docker.docker_cli is not None:
                self.docker.tool = self.runner.docker.docker_cli

    def load(self, name, config, overrides: Optional[Dict[str, Any]] = None):
        super(DockerJob, self).load(name, config, overrides=overrides)
        self.services = get_services(config, name)
        pull_policy = self.docker_pull_policy
        if pull_policy is not None:
            self.docker.pull_policy = pull_policy
        self.set_job_variables()

    def get_emulator_runner(self) -> Optional[GleRunnerConfig]:
        ctx = get_user_config_context()
        return ctx.find_runner(image=True, tags=self.tags)

    def set_job_variables(self):
        super(DockerJob, self).set_job_variables()
        all_images = self._config.get("image", None)
        self._image = self._config[self.name].get("image", all_images)
        if self.docker_image is not None:
            self.configure_job_variable("CI_JOB_IMAGE", self.docker_image, force=True)
        self.configure_job_variable("CI_DISPOSABLE_ENVIRONMENT", "true", force=True)
        self.configure_job_variable("CI_PROJECT_DIR", self.inside_workspace)
        self.configure_job_variable("CI_BUILDS_DIR", os.path.dirname(self.inside_workspace))

    def abort(self):
        """
        Abort the build by killing our container
        :return:
        """
        info("abort docker job {}".format(self.name))
        # we need to wait for the container to start
        if self.docker.container is None:
            time.sleep(1)

        if self.container and self.docker.container:
            info("kill container {}".format(self.name))
            self.docker.kill()
        if self.build_process is not None:
            try:  # pragma: no cover
                if self.build_process.poll() is None:
                    self.build_process.terminate()
            except Exception as err:  # pragma: no cover
                assert err is not None

    def get_envs(self, expand_only_ci=True):
        """
        Get env vars for a docker job
        :return:
        """
        envs = self.base_variables()
        return self.get_defined_envs(envs, expand_only_ci=expand_only_ci)

    def run_script(self, lines):
        return self._run_script(lines)

    def _run_script(self, lines, attempts=2, user=None):
        task = None
        if user is None:
            if self.shell_is_user:  # pragma: cover if posix
                user = self._shell_uid

        filename = "generated-gitlab-script" + self.get_script_fileext()
        temp = os.path.join(tempfile.gettempdir(), filename)
        try:
            with open(temp, "w") as fd:
                print(lines, file=fd)
            # copy it to the container
            dest = "/tmp"
            if is_windows():  # pragma: cover if windows
                dest = "c:\\windows\\temp"
            target_script = os.path.join(dest, filename)
            info("Copying {} to container as {} ..".format(temp, target_script))
            self.docker.add_file(temp, dest)

            while attempts > 0:
                try:
                    interactive = bool(self.enter_shell or self.error_shell)
                    if interactive:  # pragma: no cover
                        try:
                            if not os.isatty(sys.stdin.fileno()):
                                interactive = False
                        except OSError:
                            # probably under pycharm pytest
                            interactive = False
                    cmdline = self.shell_command(target_script)
                    task = self.docker.exec(self.inside_workspace,
                                            cmdline,
                                            tty=interactive,
                                            user=user)
                    self.communicate(task, script=None)
                    break
                except DockerExecError:  # pragma: no cover
                    self.stdout.write(
                        "Warning: docker exec error - https://gitlab.com/cunity/gitlab-emulator/-/issues/10")
                    attempts -= 1
                    if attempts == 0:
                        raise
                    else:
                        time.sleep(2)
            return task
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def check_docker_exec_failed(self, line):
        """
        Raise an error if the build script has returned "No such exec instance"
        :param line:
        :return:
        """
        if line:
            try:
                decoded = line.decode()
            except Exception:
                return
            if decoded:
                if "No such exec instance" in decoded:
                    raise DockerExecError()

    def communicate(self, process, script=None):
        comm(process, self.stdout, script=script, linehandler=self.check_docker_exec_failed)

    def has_bash(self):
        """
        Return True of the container has bash
        :return:
        """
        if self._has_bash is None:
            self._has_bash = False
            if not is_windows():
                info("checking container for bash")
                try:
                    self.docker.check_call(
                        self.inside_workspace, ["sh", "-c", "command -v bash"],
                        capture=True,
                        stderr=subprocess.STDOUT)
                    self._has_bash = True
                except subprocess.CalledProcessError as cpe:
                    assert cpe
        return self._has_bash

    def shell_on_error(self):
        """
        Execute a shell command on job errors
        :return:
        """
        print("Job {} script error..".format(self.name), flush=True)
        lines = "\n".join(self.error_shell)
        self.run_script(lines)

    def git_safe_dir(self):
        """Configure git safe.directory if possible"""
        info("attempting to set git safe.directory..")
        folder = self.inside_workspace
        cmdline = f"command -v git 2>&1 >/dev/null && git config --global --add safe.directory '{folder}'"
        if is_windows():  # pragma: cover if windows
            folder = folder.replace("\\", "/")  # windows git won't understand \ chars for this
            cmdline = f"git config --global --add safe.directory {folder}"
        info(f"running {cmdline}")
        self.run_script(cmdline)

    def run_impl(self):
        info(f"running docker job {self.name}")
        info(f"runner = {self.runner}")
        from .resnamer import generate_resource_name
        if is_windows():  # pragma: cover if windows
            warning("warning windows docker is experimental")
        if self.runner.docker is None:
            raise GitlabEmulatorError("docker not detected")

        with self._container_lock:
            self.docker.image = self.docker_image
            self.container = generate_resource_name()
            self.docker.name = self.container
            if not is_windows():  # pragma: cover if not windows
                if self.runner.docker:
                    self.docker.privileged = self.runner.docker.privileged

            if not is_windows():  # pragma: cover if not windows
                image_name = self.docker.image
                image_name = image_name.split("/")[-1].split("@")[0].split(":")[0]
                if self.error_shell or self.enter_shell:
                    self.docker.add_env("PS1", f"[{self.name}] \\u@{image_name}:$PWD $ ")

            if self.docker.pull_always or (self.docker.pull_if_not_present and not self.docker.image_present):
                self.docker.pull()

            environ = self.get_envs(expand_only_ci=False)
            with docker_services(self, environ) as network:
                if network:
                    self.docker.network = network
                for envname in environ:
                    self.docker.add_env(envname, environ[envname])

                if self.docker_entrypoint is not None:
                    if is_windows():  # pragma: cover if windows
                        # windows can't have multiple args
                        args = self.docker_entrypoint
                        if len(args) > 0:
                            if len(args) > 1:
                                warning("windows docker entrypoint override may fail with several args")
                            self.docker.entrypoint = args[0]
                    else:
                        self.docker.entrypoint = self.docker_entrypoint
                volumes = self.runner.docker.runtime_volumes()
                if volumes:
                    info("Extra docker volumes registered:")
                    for item in volumes:
                        info("- {}".format(item))

                self.docker.volumes = volumes + [f"{self.workspace}:{self.inside_workspace}:rw"]

                self.docker.run()

                if not is_windows():  # pragma: cover if not windows
                    # work out default USER from the image
                    docker_user_cfg = self.docker.get_user()
                    if docker_user_cfg and ":" in docker_user_cfg:
                        info(f"Container image defines USER: {docker_user_cfg}")
                        docker_user, docker_grp = docker_user_cfg.split(":", 1)
                        info(f"Setting ownership to {docker_user}:{docker_grp}")
                        self._run_script(f"chown -R {docker_user}.{docker_grp} .", attempts=1, user="0")

                if self.shell_is_user:
                    if not is_windows():  # pragma: cover if not windows
                        # try to make a more functional user account inside the container, this may not always
                        # work due to missing tools, but it's worth a try
                        _homedir = "/gle-tmp-home"
                        _passwd = f"gle:x:{self._shell_uid}:{self._shell_gid}:gitlab-emulator:{_homedir}:/bin/sh"
                        _shadow = f"gle:!:{self._shell_uid}::::::"
                        try:
                            info(f"setting up interactive user with uid={self._shell_uid}..")
                            self.docker.check_call("/",
                                                   ["sh", "-c", f"echo {_passwd} >> /etc/passwd"], capture=True)
                            self.docker.check_call("/",
                                                   ["sh", "-c", f"echo {_shadow} >> /etc/shadow"], capture=True)
                            self.docker.check_call("/",
                                                   ["mkdir", _homedir], capture=True)
                            self.docker.check_call("/",
                                                   ["chown", str(self._shell_uid), _homedir], capture=True)
                            self.docker.check_call("/",
                                                   ["chgrp", str(self._shell_gid), _homedir], capture=True)
                            # append this user to the sudoers file
                            info(f"granting sudo inside container..")
                            self.docker.check_call("/",
                                                   ["sh", "-c", f"echo 'gle ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers"])
                            info("interactive user setup completed.")
                        except subprocess.CalledProcessError:
                            warning("interactive user setup failed, some features may not work fully.")

                self.git_safe_dir()

                try:
                    lines = self.before_script + self.script
                    if self.enter_shell:
                        lines.extend(self.get_interactive_shell_command())

                    self.build_process = self.run_script(make_script(lines, powershell=self.is_powershell()))
                finally:
                    try:
                        if self.error_shell:  # pragma: no cover
                            if not self.build_process or self.build_process.returncode:
                                self.shell_on_error()
                        if self.after_script:
                            info("Running after_script..")
                            self.run_script(make_script(self.after_script, powershell=self.is_powershell()))
                    except subprocess.CalledProcessError:  # pragma: no cover
                        pass
                    finally:
                        subprocess.call([self.docker.tool, "kill", self.container], stderr=subprocess.STDOUT)
                        if self.docker.is_windows_hyperv():  # pragma: no cover
                            subprocess.call([self.docker.tool, "rm", self.container])

        result = self.build_process.returncode
        if result:
            fatal("Docker job {} failed".format(self.name))


def get_services(config, jobname):
    """
    Get the service containers that should be started for a particular job
    :param config:
    :param jobname:
    :return:
    """
    job = config.get(jobname)

    services = []
    service_defs = []

    if "image" in config or "image" in job:
        # yes we are using docker, so we can offer services for this job
        all_services = config.get("services", [])
        job_services = job.get("services", [])
        services = all_services + job_services

    for service in services:
        item = {}
        # if this is a dict use the extended version
        # else make extended versions out of the single strings
        if isinstance(service, str):
            item["name"] = service

        # if this is a dict, it needs to at least have name but could have
        # alias and others
        if isinstance(service, dict):
            assert "name" in service
            item = service

        if item:
            service_defs.append(item)

    return service_defs


@contextmanager
def docker_services(job: DockerJob, variables: Dict[str, str]):
    """
    Setup docker services required by the given job
    :param job:
    :param variables: dict of env vars to set in the service container
    :return:
    """
    services = job.services
    service_network = None
    containers = []
    try:
        if services:
            net_name = "gle-service-network"
            try:
                job.docker.docker_call("network", "inspect", net_name)
            except DockerToolFailed:
                job.docker.docker_call(
                    "network", "create",
                    "--driver", "bridge",
                    "--subnet", "192.168.94.0/24",
                    net_name
                )

            for service in services:
                aliases = []
                if isinstance(service, str):
                    image = service
                    service = {
                        "name": image
                    }
                else:
                    image = service["name"]
                name = image
                if ":" in name:
                    name = image.split(":", 1)[0]
                aliases.append(name.replace("/", "-"))
                if "alias" in service:
                    aliases.append(service["alias"])

                job.stdout.write(f"create docker service : {name} ({aliases})\n")
                if job.docker.can_pull:
                    try:
                        job.stdout.write(f"pulling {image} ..\n")
                        job.docker.docker_call("pull", image)
                    except DockerToolFailed:  # pragma: no cover
                        fatal(f"No such image {image}")
                priv = not is_windows()
                service_cmdline = [
                    "run",
                    "--rm",
                    "-d",
                ]
                if priv:  # pragma: cover if not windows
                    service_cmdline.append("--privileged")
                for name, value in variables.items():
                    service_cmdline.extend(["-e", f"{name}={value}"])
                service_cmdline.append(image)

                container = job.docker.docker_call(
                    *service_cmdline
                ).stdout.strip()

                info(f"creating docker service {name} ({aliases})")
                info(f"service {name} is container {container}")
                containers.append(container)
                info(f"connect {name} to service network")
                connect_cmdline = [
                    "network", "connect"
                ]
                for alias in aliases:
                    connect_cmdline.extend(["--alias", alias])
                connect_cmdline.extend([net_name, container])
                job.docker.docker_call(*connect_cmdline)
                service_network = net_name

        yield service_network
    finally:
        for container in containers:
            info(f"clean up docker service {container}")
            job.docker.docker_call("kill", "-s", "9", container)
        time.sleep(1)
