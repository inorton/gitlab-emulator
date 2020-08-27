import platform
import subprocess
import time
import uuid
from contextlib import contextmanager
from .logmsg import warning, info, fatal
from .jobs import Job, make_script
from .helpers import communicate as comm, DockerTool
from .errors import DockerExecError


@contextmanager
def docker_services(job):
    """
    Setup docker services required by the given job
    :param config:
    :param jobname:
    :return:
    """
    services = job.services
    network = None
    containers = []
    try:
        if services:
            # create a network, start each service attached
            network = "gitlabemu-services-{}".format(str(uuid.uuid4())[0:4])
            info("create docker service network")
            subprocess.check_call(["docker", "network", "create",
                                   "-d", "bridge",
                                   "--subnet", "192.168.94.0/24",
                                   network
                                   ])
            # this could be a list of images
            for service in services:
                job.stdout.write("create docker service : {}".format(service))
                assert ":" in service["name"]
                image = service["name"]
                name = service["name"].split(":", 1)[0]
                aliases = [name]
                if "alias" in service:
                    aliases.append(service["alias"])
                try:
                    pull = subprocess.Popen(["docker", "pull", image],
                                            stdin=None,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)
                    job.check_communicate(pull)
                except subprocess.CalledProcessError:
                    warning("could not pull {}".format(image))
                docker_cmdline = ["docker", "run", "-d", "--rm"]
                if platform.system() == "Linux":
                    docker_cmdline.append("--privileged")
                docker_cmdline.append(image)
                info("creating docker service {}".format(name))
                container = subprocess.check_output(docker_cmdline).strip()
                info("service {} is container {}".format(name, container))
                containers.append(container)

                network_cmd = ["docker", "network", "connect"]
                for alias in aliases:
                    info("adding docker service alias {}".format(alias))
                    network_cmd.extend(["--alias", alias])
                network_cmd.append(network)
                network_cmd.append(container)
                subprocess.check_call(network_cmd)
        yield network
    finally:
        for container in containers:
            info("clean up docker service {}".format(container))
            subprocess.call(["docker", "kill", container])
        if network:
            info("clean up docker network {}".format(network))
            subprocess.call(["docker", "network", "rm", network])


class DockerJob(Job):
    """
    Run a job inside a docker container
    """
    def __init__(self):
        super(DockerJob, self).__init__()
        self.image = None
        self.services = []
        self.container = None
        self.entrypoint = None
        self.docker = DockerTool()

    def load(self, name, config):
        super(DockerJob, self).load(name, config)
        all_images = config.get("image", None)
        self.image = config[name].get("image", all_images)
        self.configure_job_variable("CI_JOB_IMAGE", self.image)
        self.services = get_services(config, name)

    def abort(self):
        """
        Abort the build by killing our container
        :return:
        """
        info("abort docker job {}".format(self.name))
        if self.container:
            info("kill container {}".format(self.name))
            subprocess.call(["docker", "kill", self.container])

    def get_envs(self):
        """
        Get env vars for a docker job
        :return:
        """
        return dict(self.variables)

    def run_script(self, lines):
        return self._run_script(lines)

    def _run_script(self, lines, attempts=2):
        task = None
        while attempts > 0:
            try:
                task = self.docker.exec(self.workspace, self.shell)
                self.communicate(task, script=lines.encode())
                break
            except DockerExecError:
                self.stdout.write("Warning: docker exec error - https://gitlab.com/cunity/gitlab-emulator/-/issues/10")
                attempts -= 1
                if attempts == 0:
                    raise
                else:
                    time.sleep(2)
        return task

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

    def run(self):
        if platform.system() == "Windows":
            warning("warning windows docker is experimental")
        
        if platform.system() == "Linux":
            self.docker.privileged = True

        if isinstance(self.image, dict):
            image = self.image["name"]
            self.entrypoint = self.image.get("entrypoint", self.entrypoint)
            self.image = image

        self.docker.image = self.image
        self.container = "gitlab-emu-" + str(uuid.uuid4())
        self.docker.name = self.container

        info("pulling docker image {}".format(self.image))
        try:
            self.stdout.write("Pulling {}...".format(self.image))
            pull = self.docker.pull()
            self.check_communicate(pull)
        except subprocess.CalledProcessError:
            warning("could not pull docker image {}".format(self.image))

        with docker_services(self) as network:
            if network:
                self.docker.network = network

            environ = self.get_envs()
            for envname in environ:
                self.docker.env[envname] = environ[envname]

            if self.entrypoint is not None:
                self.docker.entrypoint = self.entrypoint

            self.docker.volumes = ["{}:{}".format(self.workspace, self.workspace)]

            self.docker.run()

            try:
                self.build_process = self.run_script(make_script(self.before_script + self.script))
            finally:
                self.run_script(make_script(self.after_script))
                try:
                    if self.error_shell:
                        try:
                            print("Running error-shell..")
                            subprocess.check_call(["docker", "exec", "-it", self.container] + self.error_shell)
                        except subprocess.CalledProcessError:
                            pass
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
