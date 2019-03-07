"""
Represent a gitlab job
"""
from __future__ import print_function
import os
import sys
import subprocess
import shutil
import tempfile
from . import configloader
from .errors import GitlabEmulatorError


class NoSuchJob(GitlabEmulatorError):
    """
    Could not find a job with the given name
    """
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "NoSuchJob {}".format(self.name)


class Job(object):
    """
    A Gitlab Job
    """
    def __init__(self):
        self.before_script = []
        self.script = []
        self.after_script = []
        self.tags = []
        self.stage = None
        self.variables = {}

    def load(self, name, config):
        """
        Load a job from a dictionary
        :param name:
        :param config:
        :return:
        """
        job = config[name]
        all_before = config.get("before_script", [])
        self.before_script = job.get("before_script", all_before)
        self.script = job.get("script", [])
        all_after = config.get("after_script", [])
        self.after_script = job.get("after_script", all_after)
        self.variables = job.get("variables", {})
        self.tags = job.get("tags", [])

    def run(self):
        """
        Run the job on the local machine
        :return:
        """
        envs = dict(os.environ)
        for name in self.variables:
            envs[name] = self.variables[name]
        try:
            lines = self.before_script + self.script + self.after_script
            script = make_script(lines)
            try:
                tmpdir = tempfile.mkdtemp(dir=os.getcwd())
                filename = os.path.join(tmpdir, "gitlab-emu-tmp")
                with open(filename, "w") as scriptfile:
                    scriptfile.write(script)
                os.chmod(filename, 0700)
                subprocess.check_call([filename])
            finally:
                shutil.rmtree(tmpdir)

        except subprocess.CalledProcessError:
            print("Failed running job {}".format(self.name))
            sys.exit(1)


class DockerJob(Job):
    """
    Run a job inside a docker container
    """
    def __init__(self):
        super(DockerJob, self).__init__()
        self.image = None

    def load(self, name, config):
        super(DockerJob, self).load(name, config)
        all_images = config.get("image", None)
        self.image = config[name].get("image", all_images)

    def run(self):
        raise NotImplementedError()


def make_script(lines):
    """
    Join lines together to make a script
    :param lines:
    :return:
    """
    content = os.linesep.join(lines)
    return content


def load(config, name):
    """
    Load a job from the configuration
    :param config:
    :param name:
    :return:
    """
    jobs = configloader.get_jobs(config)
    if name not in jobs:
        raise NoSuchJob(name)

    if config.get("image") or config[name].get("image"):
        job = DockerJob()
    else:
        job = Job()
    job.load(name, config)
    return job
