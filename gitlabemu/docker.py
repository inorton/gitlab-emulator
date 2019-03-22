from __future__ import print_function
import os
import platform
import subprocess
import sys
import uuid
from contextlib import contextmanager

from .jobs import Job, make_script


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
            subprocess.check_call(["docker", "network", "create",
                                   "-d", "bridge",
                                   "--subnet", "192.168.94.0/24",
                                   network
                                   ])
            # this could be a list of images
            for service in services:
                assert ":" in service["name"]
                image = service["name"]
                name = service["name"].split(":", 1)[0]
                aliases = [name]
                if "alias" in service:
                    aliases.append(service["alias"])
                try:
                    subprocess.check_call(["docker", "pull", image])
                except subprocess.CalledProcessError:
                    print("warning: could not pull {}".format(image))
                container = subprocess.check_output(
                    ["docker", "run",
                     "--privileged",
                     "-d", "--rm",
                     image]).strip()
                containers.append(container)

                network_cmd = ["docker", "network", "connect"]
                for alias in aliases:
                    print("adding alias {}".format(alias))
                    network_cmd.extend(["--alias", alias])
                network_cmd.append(network)
                network_cmd.append(container)
                subprocess.check_call(network_cmd)

        yield network
    finally:
        for container in containers:
            subprocess.call(["docker", "kill", container])
        if network:
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

    def load(self, name, config):
        super(DockerJob, self).load(name, config)
        all_images = config.get("image", None)
        self.image = config[name].get("image", all_images)
        self.services = get_services(config, name)

    def run(self):
        if platform.system() == "Windows":
            print("warning windows docker is experimental")
        if isinstance(self.image, dict):
            image = self.image["name"]
            self.entrypoint = self.image.get("entrypoint", self.entrypoint)
            self.image = image
        # squirt the script into the container stdin like gitlab does
        lines = self.before_script + self.script + self.after_script
        script = make_script(lines)

        self.container = "gitlab-emu-" + str(uuid.uuid4())

        subprocess.check_call(["docker", "pull", self.image])

        with docker_services(self) as network:
            cmdline = ["docker",
                       "run",
                       "--rm", "--name", self.container,
                       "-w", os.getcwd(), "-v",
                       os.getcwd() + ":" + os.getcwd(), "-i"]

            if network:
                cmdline.extend(["--network", network])

            for envname in self.variables:
                cmdline.extend(["-e", "{}={}".format(envname,
                                                     self.variables[envname])])

            if self.entrypoint is not None:
                cmdline.extend(["--entrypoint", " ".join(self.entrypoint)])

            cmdline.append(self.image)

            opened = subprocess.Popen(cmdline,
                                      stdin=subprocess.PIPE,
                                      stdout=sys.stdout,
                                      stderr=sys.stderr)

            opened.communicate(input=script)

        result = opened.returncode
        if result:
            print("Docker job {} failed".format(self.name))
            sys.exit(1)


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
