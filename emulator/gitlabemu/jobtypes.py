"""Abstraction layer for different kinds of jobs"""
import shlex
import textwrap
from typing import Optional, Union, Dict, Any
from .jobs import Job, make_script
from .docker import DockerJob
from .helpers import is_windows


class JobFactory:
    base_class = Job
    docker_class = DockerJob

    def new_job(self, image: Optional[Union[str, Dict[str, Any]]] = None):
        if image is not None:
            return self.docker_class()
        return self.base_class()


class ScriptJob(Job):
    """A job that simply prints a script that will run the job"""

    def is_powershell(self) -> bool:
        return False

    def run_impl(self):
        lines = self.before_script + self.script
        script = make_script(lines, powershell=self.is_powershell())
        print(script)


class PowershellJob(ScriptJob):
    def is_powershell(self) -> bool:
        return True


class DockerScriptJob(DockerJob):
    """A script output job that includes container setup and teardown"""

    def is_powershell(self) -> bool:
        return False

    def run_impl(self):
        if self.services:
            raise NotImplementedError("docker service script setup not supported yet")

        # make the job content
        lines = self.before_script + self.script

        inner_script = "echo generated ci job\nset -x\n" + make_script(lines, powershell=self.is_powershell())
        inner_script += "echo complete"
        environ = self.get_envs(expand_only_ci=True)
        env_args = []
        for item, value in environ.items():
            value = shlex.quote(value)
            env_args.extend(["-e", f"{item}={value}"])
        docker_run = f"docker run -v $(pwd):$(pwd) -w $(pwd) --rm {' '.join(env_args)} -i {self.docker_image}"

        # make a heredoc
        script = f"#!/bin/sh\nset -ex\ncat <<DOCKEREOF |\n{inner_script}\nDOCKEREOF\n {docker_run} sh\n"
        print(script)


class DockerPowershellJob(DockerJob):
    """Generate a powershell script for windows docker jobs"""
    def is_powershell(self) -> bool:
        return True

    def run_impl(self):
        if self.services:
            raise NotImplementedError("docker service script setup not supported yet")
        # make the job content
        lines = self.before_script + self.script
        inner_script = "echo \"generated ci job\"\r\n" + make_script(lines, powershell=self.is_powershell())




class ScriptJobFactory(JobFactory):
    base_class = ScriptJob
    docker_class = DockerScriptJob
