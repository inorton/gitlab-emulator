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
                if ":" in service:
                    name = service.split(":", 1)[0]
                else:
                    name = service  # bad?
                    service = name + ":latest"  # ????
                subprocess.check_call(["docker", "pull", service])
                container = subprocess.check_output(
                    ["docker", "run",
                     "--privileged",
                     "-d", "--rm",
                     service]).strip()
                containers.append(container)
                print("added {} to {} alias {}".format(container, network,
                                                       name))
                subprocess.check_call(
                    ["docker", "network", "connect",
                     "--alias", name,
                     network,
                     container])
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
        self.services = config[name].get("services", self.services)

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
