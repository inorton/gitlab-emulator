"""Classes that represent generic CI jobs"""
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

from ..docker import DockerJob
from ..jobs import Job


class ToDict(ABC):

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass


class GenericContainerSpec(ToDict):
    def __init__(self):
        self.image: str = ""
        self.entrypoint: Optional[List[str]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image": self.image,
            "entrypoint": self.entrypoint
        }


class GenericContainerServiceSpec(GenericContainerSpec):
    def __init__(self):
        super(GenericContainerServiceSpec, self).__init__()
        self.alias: Optional[str] = None
        self.command: List[str] = []
        self.variables: Dict[str, str] = {}

    def to_dict(self) -> Dict[str, Any]:
        basedata = super(GenericContainerServiceSpec, self).to_dict()
        basedata.update({
            "alias": self.alias,
            "command": self.command,
            "variables": self.variables
        })
        return basedata


class GenericDependency(ToDict):
    def __init__(self):
        self.job: str = ""
        self.need_artifacts: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job": self.job,
            "artifacts": self.need_artifacts
        }


class GenericArtifacts(ToDict):
    def to_dict(self) -> Dict[str, Any]:
        return {
            "if_failed": self.if_failed,
            "if_success": self.if_success,
            "paths": self.paths
        }

    def __init__(self):
        self.if_failed: bool = False
        self.if_success: bool = True
        self.paths: List[str] = []


class GenericJob(ToDict):
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "stage_name": self.stage_name,
            "depends": [x.to_dict() for x in self.needed_jobs],
            "set_variables": self.set_variables,
            "machine_tags": self.machine_tags,
            "container": self.container.to_dict(),
            "services": [x.to_dict() for x in self.services],
            "job_script": {
                "lines": self.job_script_lines,
                "exit_on_nonzero": True,
                "fail_on_nonzero": True
            },
            "finally_script": {
                "lines": self.finally_script_lines,
                "exit_on_nonzero": True,
                "fail_on_nonzero": False
            },
            "artifacts": self.artifacts.to_dict()
        }

    def __init__(self):
        self.name: str = ""
        self.stage_name: str = ""
        self.needed_jobs: List[GenericDependency] = []
        self.machine_tags: List[str] = []
        self.set_variables: Dict[str, str] = {}
        self.container: GenericContainerSpec = GenericContainerSpec()
        self.services: List[GenericContainerServiceSpec] = []
        self.job_script_lines: List[str] = []
        self.finally_script_lines: List[str] = []
        self.artifacts: GenericArtifacts = GenericArtifacts()

    def from_job(self, loader, job: Job):
        self.name = job.name
        self.stage_name = job.stage
        self.job_script_lines = job.before_script + job.script
        self.finally_script_lines = job.after_script
        self.machine_tags = job.tags
        self.set_variables = job.variables
        self.set_variables["CI_JOB_NAME"] = job.name
        if job.stage:
            self.set_variables["CI_JOB_STAGE"] = job.stage
        if job.parallel:
            self.set_variables["CI_NODE_TOTAL"] = "1"
            self.set_variables["CI_NODE_INDEX"] = "1"
        for dep in job.dependencies:
            depend = GenericDependency()
            depend.job = dep
            depend.need_artifacts = dep in job.needed_artifacts
            self.needed_jobs.append(depend)

        if job.artifacts:
            if job.artifacts.when == "on_success":
                self.artifacts.if_failed = False
            elif job.artifacts.when == "always":
                self.artifacts.if_failed = True
            elif job.artifacts.when == "on_failure":
                self.artifacts.if_success = False
            self.artifacts.paths = job.artifacts.paths

        if isinstance(job, DockerJob):
            image = loader.get_docker_image(self.name)
            if isinstance(image, str):
                self.container.image = image
            else:
                self.container.image = image["name"]
                self.container.entrypoint = image.get("entrypoint", [])
            if job.services:
                for service in job.services:
                    svc = GenericContainerServiceSpec()
                    svc.variables.update(self.set_variables)
                    svc.image = service.get("name")
                    svc.alias = service.get("alias", None)
                    self.services.append(svc)
