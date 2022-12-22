import os
import shutil
import subprocess
import sys
import tempfile
import time
import tarfile
from contextlib import contextmanager
from typing import Dict, Optional, List

from .logmsg import warning, info, fatal
from .jobs import Job, make_script
from .helpers import communicate as comm, is_windows
from .userconfig import get_user_config_context
from .errors import DockerExecError
from .dockersupport import docker
from .variables import expand_variable


class DockerTool(object):
    """
    Control docker containers
    """
    def __init__(self, retries: Optional[int] = 5):
        self.retries = retries
        self.container = None
        self.image = None
        self.env = {}
        self.volumes = []
        self.name = None
        self.privileged = False
        self.entrypoint = None
        self.pulled = None
        self.network = None
        self._client = None

    @property
    def client(self):
        from docker.errors import DockerException
        if not self._client:
            retry_sleep = 10
            errors = 0
            while True:
                try:
                    self._client = docker.from_env()
                    break
                except DockerException as err:  # pragma: no cover
                    errors += 1
                    if errors > self.retries:
                        raise
                    warning(f"cannot connect to docker daemon {err}")
                    warning(f"retry in {retry_sleep} seconds")
                    time.sleep(retry_sleep)
        return self._client

    def add_volume(self, outside, inside):
        self.volumes.append("{}:{}".format(outside, inside))

    def add_env(self, name, value):
        self.env[name] = value

    def inspect(self):
        """
        Inspect the image and return the Config dict
        :return:
        """
        if self.image:
            self.pull()
            return self.client.images.get(self.image)
        return None

    def add_file(self, src, dest):
        """
        Copy a file to the container
        :param src:
        :param dest:
        :return:
        """
        assert self.container
        temp = tempfile.mkdtemp()
        tar = os.path.join(temp, "add.tar")
        try:
            with tarfile.open(tar, "w") as tf:
                tf.add(src, os.path.basename(src))
            with open(tar, "rb") as td:
                data = td.read()
            self.container.put_archive(dest, data)
        finally:
            shutil.rmtree(temp)

    def get_user(self):
        image = self.inspect()
        if image:
            return image.attrs["Config"].get("User", None)
        return None

    def pull(self):
        self.client.images.pull(self.image)

    def get_envs(self):
        cmdline = []
        for name in self.env:
            value = self.env.get(name)
            if value is not None:
                cmdline.extend(["-e", "{}={}".format(name, value)])
            else:
                cmdline.extend(["-e", name])
        return cmdline

    def wait(self):
        self.container.wait()

    def run(self):
        priv = self.privileged and not is_windows()
        volumes = []
        for volume in self.volumes:
            entry = volume
            if not entry.endswith(":ro") and not entry.endswith(":rw"):
                entry += ":rw"
            volumes.append(entry)

        image = self.inspect()
        if self.entrypoint == ['']:
            if image.attrs["Os"] == "linux":
                self.entrypoint = ["/bin/sh"]
            else:
                self.entrypoint = None
        try:
            self.container = self.client.containers.run(
                self.image,
                detach=True,
                stdin_open=True,
                remove=True,
                name=self.name,
                privileged=priv,
                network=self.network,
                entrypoint=self.entrypoint,
                volumes=volumes,
                environment=self.env
            )
        except Exception:
            warning(f"problem running {self.image}")
            raise

    def kill(self):
        if self.container:
            self.container.kill()

    def check_call(self, cwd, cmd, stdout=None, stderr=None):
        cmdline = ["docker", "exec", "-w", cwd, self.container.id] + cmd
        subprocess.check_call(cmdline, stdout=stdout, stderr=stderr)

    def exec(self, cwd, shell, tty=False, user=None, pipe=True):
        cmdline = ["docker", "exec", "-w", cwd]
        cmdline.extend(self.get_envs())
        if user is not None:
            cmdline.extend(["-u", str(user)])
        if tty:
            cmdline.append("-t")
            pipe = False
        cmdline.extend(["-i", self.container.id])
        cmdline.extend(shell)

        if pipe:
            proc = subprocess.Popen(cmdline,
                                    shell=False,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            return proc
        else:
            return subprocess.call(cmdline, shell=False)


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

    def load(self, name, config):
        all_images = config.get("image", None)
        self._image = config[name].get("image", all_images)
        self.services = get_services(config, name)
        super(DockerJob, self).load(name, config)

    def set_job_variables(self):
        super(DockerJob, self).set_job_variables()
        self.configure_job_variable("CI_JOB_IMAGE", str(self.docker_image), force=True)
        self.configure_job_variable("CI_DISPOSABLE_ENVIRONMENT", "true", force=True)
        self.configure_job_variable("CI_PROJECT_DIR", self.inside_workspace)
        self.configure_job_variable("CI_BUILDS_DIR", os.path.dirname(self.inside_workspace))

    def abort(self):
        """
        Abort the build by killing our container
        :return:
        """
        info("abort docker job {}".format(self.name))
        if self.container:
            info("kill container {}".format(self.name))
            subprocess.call(["docker", "kill", self.container])

    def get_envs(self, expand_only_ci=True):
        """
        Get env vars for a docker job
        :return:
        """
        ret = self.base_variables()

        for name in self.variables:
            value = self.variables[name]
            if value is None:
                value = ""
            ret[name] = value

        for name in self.extra_variables:
            ret[name] = self.extra_variables[name]
        return self.expand_variables(ret, only_ci=expand_only_ci)

    def run_script(self, lines):
        return self._run_script(lines)

    def _run_script(self, lines, attempts=2, user=None):
        task = None
        filename = "generated-gitlab-script" + self.get_script_fileext()
        temp = os.path.join(tempfile.gettempdir(), filename)
        try:
            with open(temp, "w") as fd:
                print(lines, file=fd)
            # copy it to the container
            dest = "/tmp"
            if is_windows():  # pragma: linux no cover
                dest = "c:\\windows\\temp"
            target_script = os.path.join(dest, filename)
            info("Copying {} to container as {} ..".format(temp, target_script))
            self.docker.add_file(temp, dest)

            while attempts > 0:
                try:
                    cmdline = self.shell_command(target_script)
                    task = self.docker.exec(self.inside_workspace, cmdline, user=user)
                    self.communicate(task, script=None)
                    break
                except DockerExecError:
                    self.stdout.write(
                        "Warning: docker exec error - https://gitlab.com/cunity/gitlab-emulator/-/issues/10")
                    attempts -= 1
                    if attempts == 0:
                        raise
                    else:
                        time.sleep(2)
            return task
        finally:
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
        if not is_windows():
            try:
                self.docker.check_call(self.inside_workspace, ["which", "bash"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except subprocess.CalledProcessError:
                pass
        return False

    def shell_on_error(self):
        """
        Execute a shell command on job errors
        :return:
        """
        print("Job {} script error..".format(self.name), flush=True)
        self.run_shell(self.error_shell, run_before=False)

    def run_shell(self, cmdline=None, run_before=False):
        uid = 0
        if cmdline is str:
            cmdline = [cmdline]

        # set the defaults
        if cmdline is None:
            if is_windows():  # pragma: linux no cover
                if self.is_powershell():
                    cmdline = ["powershell.exe"]
                else:
                    cmdline = ["cmd.exe"]
            else:
                try_bash = self.has_bash()
                if self.shell_is_user:
                    uid = os.getuid()
                cmdline = ["/bin/sh"]
                if try_bash:
                    cmdline = ["bash"]
        
        if not is_windows():
            # set a prompt
            image_base = self.docker.image
            if "/" in image_base:
                image_base = image_base.split("/")[-1].split("@")[0]
            self.docker.add_env("PS1", f"{cmdline} `whoami`@{image_base}:$PWD $ ")
        else:
            # pragma: linux no cover
            # make interactive shells work on windows
            uid = ""

        print("Running interactive-shell..", flush=True)
        try:
            tty = sys.stdin.isatty()
            if not run_before:
                self.docker.exec(self.inside_workspace, cmdline, tty=tty, user=uid, pipe=False)
            else:
                print("Running before_script..", flush=True)
                # create the before script, copy it to the container and run it
                script_file = tempfile.mktemp()
                with open(script_file, "w") as script:
                    script.write(make_script(self.before_script + cmdline))
                try:
                    self.docker.add_file(script_file, script_file)
                    self.docker.exec(self.inside_workspace, ["/bin/sh", script_file], tty=tty, user=uid, pipe=False)
                finally:
                    os.unlink(script_file)

        except subprocess.CalledProcessError:
            pass

    def run_impl(self):
        from .resnamer import generate_resource_name
        if is_windows():  # pragma: linux no cover
            warning("warning windows docker is experimental")

        if not is_windows():
            self.docker.privileged = True
        self.docker.image = self.docker_image
        self.container = generate_resource_name()
        self.docker.name = self.container

        info("pulling docker image {}".format(self.docker.image))
        try:
            self.stdout.write("Pulling {}...\n".format(self.docker.image))
            self.docker.pull()
        except subprocess.CalledProcessError:
            warning("could not pull docker image {}".format(self.docker.image))

        environ = self.get_envs(expand_only_ci=False)
        with docker_services(self, environ) as network:
            if network:
                self.docker.network = network.name
            for envname in environ:
                self.docker.env[envname] = environ[envname]

            if self.docker_entrypoint is not None:
                self.docker.entrypoint = self.docker_entrypoint
            volumes = get_user_config_context().docker.runtime_volumes()
            if volumes:
                info("Extra docker volumes registered:")
                for item in volumes:
                    info("- {}".format(item))

            self.docker.volumes = volumes + [f"{self.workspace}:{self.inside_workspace}:rw"]

            self.docker.run()

            if not is_windows():
                # work out USER
                docker_user_cfg = self.docker.get_user()
                if docker_user_cfg and ":" in docker_user_cfg:
                    docker_user, docker_grp = docker_user_cfg.split(":", 1)
                    self.stdout.write(f"Setting ownership to {docker_user}:{docker_grp}")
                    self._run_script(f"chown -R {docker_user}.{docker_grp} .", attempts=1, user="0")

            try:
                if self.enter_shell:
                    print("Entering shell")
                    self.run_shell(run_before=self.before_script_enter_shell)
                    print("Exiting shell")
                    return

                self.build_process = self.run_script(make_script(self.before_script + self.script, powershell=self.is_powershell()))
            finally:
                try:
                    if self.error_shell:
                        if not self.build_process or self.build_process.returncode:
                            self.shell_on_error()
                    if self.after_script:
                        info("Running after_script..")
                        self.run_script(make_script(self.after_script, powershell=self.is_powershell()))
                except subprocess.CalledProcessError:
                    pass
                finally:
                    subprocess.call(["docker", "kill", self.container], stderr=subprocess.STDOUT)

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


def has_docker() -> bool:
    """
    Return True if this system can run docker containers
    :return:
    """
    if docker:
        # noinspection PyBroadException
        try:
            client = docker.DockerClient()
            client.info()
            return True
        except Exception:
            pass
    return False


@contextmanager
def docker_services(job: DockerJob, variables: Dict[str, str]):
    """
    Setup docker services required by the given job
    :param job:
    :param variables: dict of env vars to set in the service container
    :return:
    """
    from .resnamer import generate_resource_name
    services = job.services
    service_network = None
    containers = []
    try:
        if services:
            client = docker.DockerClient()
            # create a network, start each service attached
            info("create docker services network")
            service_network = client.networks.create(
                generate_resource_name(),
                driver="bridge",
                ipam=docker.types.IPAMConfig(
                        pool_configs=[
                            docker.types.IPAMPool(subnet="192.168.94.0/24")
                        ]
                    )
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

                try:
                    client.images.pull(image)
                except docker.errors.ImageNotFound:
                    fatal(f"No such image {image}")
                priv = not is_windows()
                container = client.containers.run(
                    image,
                    privileged=priv,
                    environment=dict(variables),
                    remove=True, detach=True)
                info(f"creating docker service {name} ({aliases})")
                info(f"service {name} is container {container.id}")
                containers.append(container)
                info(f"connect {name} to service network")
                service_network.connect(container=container,
                                        aliases=aliases)

        yield service_network
    finally:
        for container in containers:
            info(f"clean up docker service {container.id}")
            container.kill()
        if service_network:
            info(f"clean up docker network {service_network.name}")
            service_network.remove()
