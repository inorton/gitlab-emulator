"""
Represent a gitlab job
"""
import os
import sys
import platform
import subprocess
import shutil
import tempfile
from logmsg import info, fatal
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
        self.name = None
        self.before_script = []
        self.script = []
        self.after_script = []
        self.tags = []
        self.stage = None
        self.variables = {}
        self.dependencies = []

    def load(self, name, config):
        """
        Load a job from a dictionary
        :param name:
        :param config:
        :return:
        """
        self.name = name
        job = config[name]
        all_before = config.get("before_script", [])
        self.before_script = job.get("before_script", all_before)
        self.script = job.get("script", [])
        all_after = config.get("after_script", [])
        self.after_script = job.get("after_script", all_after)

        self.variables = config.get("variables", {})
        job_vars = job.get("variables", {})
        for name in job_vars:
            self.variables[name] = job_vars[name]
        self.tags = job.get("tags", [])
        self.dependencies = job.get("dependencies", [])

        # TODO add gitlab env vars to variables

    def run(self):
        """
        Run the job on the local machine
        :return:
        """
        envs = dict(os.environ)
        for name in self.variables:
            envs[name] = self.variables[name]
        try:
            info("running shell job {}".format(self.name))
            lines = self.before_script + self.script + self.after_script
            script = make_script(lines)
            try:
                tmpdir = tempfile.mkdtemp(dir=os.getcwd())
                filename = os.path.join(tmpdir, "gitlab-emu-tmp")
                with open(filename, "w") as scriptfile:
                    scriptfile.write(script)
                os.chmod(filename, 0o700)
                cmdline = [filename]
                if "#!" not in lines[0]:
                    shell = os.getenv("SHELL", "/bin/sh")                
                    cmdline = [shell, filename]
                    
                subprocess.check_call(cmdline)
            finally:
                shutil.rmtree(tmpdir)

        except subprocess.CalledProcessError:
            fatal("Failed running job {}".format(self.name))            


def make_script(lines):
    """
    Join lines together to make a script
    :param lines:
    :return:
    """
    extra = []
    if platform.system() == "Linux":
        extra = ["set -e"]

    content = os.linesep.join(extra + lines)
    return content


