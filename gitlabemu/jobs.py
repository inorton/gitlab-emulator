"""
Represent a gitlab job
"""
import os
import sys
import platform
import subprocess
import select
import time
from .logmsg import info, fatal
from .errors import GitlabEmulatorError
from .helpers import communicate as comm


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
        self.build_process = None
        self.before_script = []
        self.script = []
        self.after_script = []
        self.error_shell = []
        self.tags = []
        self.stage = "test"
        self.variables = {}
        self.dependencies = []
        if platform.system() == "Windows":
            self.shell = [os.getenv("COMSPEC", "C:\\WINDOWS\\system32\\cmd.exe")]
        else:
            self.shell = ["/bin/sh"]
        self.workspace = None
        self.stderr = sys.stderr
        self.stdout = sys.stdout

    def load(self, name, config):
        """
        Load a job from a dictionary
        :param name:
        :param config:
        :return:
        """
        self.workspace = config["_workspace"]
        self.name = name
        job = config[name]
        self.error_shell = config.get("error_shell", [])
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
        # prefer needs over dependencies
        self.dependencies = job.get("needs", job.get("dependencies", []))

        self.configure_job_variable("CI_JOB_ID", str(int(time.time())))
        self.configure_job_variable("CI_JOB_NAME", self.name)
        self.configure_job_variable("CI_JOB_STAGE", self.stage)
        self.configure_job_variable("CI_JOB_TOKEN", "00" * 32)
        self.configure_job_variable("CI_JOB_URL", "file://gitlab-emulator/none")

    def configure_job_variable(self, name, value):
        """
        Set job variable defaults. If the variable is not present in self.variables, set it to the given value. If the variable is present in os.environ, use that value instead
        :return:
        """
        if value is None:
            value = ""
        value = str(value)

        # set job related env vars
        if name not in self.variables:
            if name in os.environ:
                value = os.environ[name]  # prefer env variables if set
            self.variables[name] = value

    def abort(self):
        """
        Abort the build and attempt cleanup
        :return:
        """
        info("aborting job {}".format(self.name))
        if self.build_process:
            info("killing child build process..")
            self.build_process.kill()

    def check_communicate(self, process, script=None):
        """
        Process STDIO for a build process but raise an exception on error
        :param process: child started by POpen
        :param script: script (eg bytezs) to pipe into stdin
        :return:
        """
        comm(process, stdout=self.stdout, script=script, throw=True)

    def communicate(self, process, script=None):
        """
        Process STDIO for a build process
        :param process: child started by POpen
        :param script: script (eg bytes) to pipe into stdin
        :return:
        """
        comm(process, stdout=self.stdout, script=script)

    def get_envs(self):
        """
        Get environment variable dict for the job
        :return:
        """
        envs = dict(os.environ)
        for name in self.variables:
            value = self.variables[name]
            if value is None:
                value = ""
            envs[name] = str(value)
        return envs

    def run_script(self, lines):
        """
        Execute a script
        :param lines:
        :return:
        """
        envs = self.get_envs()
        script = make_script(lines)
        opened = subprocess.Popen(self.shell,
                                  env=envs,
                                  cwd=self.workspace,
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
        self.build_process = opened
        self.communicate(opened, script=script.encode())

        return opened.returncode

    def run(self):
        """
        Run the job on the local machine
        :return:
        """

        info("running shell job {}".format(self.name))
        lines = self.before_script + self.script
        result = self.run_script(lines)

        self.run_script(self.after_script)

        if result:
            fatal("Shell job {} failed".format(self.name))


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

    if platform.system() == "Windows":
        content += os.linesep

    return content


