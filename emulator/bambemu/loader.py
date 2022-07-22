"""Parse a bamboo spec folder into one or more child pipelines"""
import os.path

from typing import List, Dict, Any

import yaml

from gitlabemu.types import BaseLoader, BaseJob

from .yamltypes import get_stream_loader, DocumentList

BAMBOO_FILE = "bamboo.yml"


class BamJob:
    def __init__(self):
        self.name = None
        self.key = None
        self.requirements: List[Dict[str, str]] = []
        self.artifacts: List[Dict[str, Any]] = []
        self.artifact_subscriptions = []
        self.tasks: List[Dict[str, Any]] = []

    def load(self, data: dict):
        self.key = data.get("key")
        self.artifacts = data.get("artifacts", [])
        self.artifact_subscriptions = data.get("artifact-subscriptions", [])
        self.requirements = data.get("requirements", [])
        self.tasks = data.get("tasks", [])

class BamStage:
    """A bamboo stage"""
    def __init__(self):
        self.name = None
        self.jobs = []
        self.final = False
        self.manual = False

    def load(self, data: dict):
        self.jobs = data.get("jobs", [])
        self.final = data.get("final", False)
        self.manual = data.get("manual", False)


class BamPlan:
    """A bamboo plan"""

    def __init__(self):
        self.name = None
        self.project_key = None
        self.key = None
        self.stages: List[BamStage] = []
        self.jobs: Dict[str, BamJob] = {}
        self.repos: List[Dict[str, Any]] = []

    def load(self, data: dict):
        self.key = data.get("plan", {}).get("key")
        self.project_key = data.get("plan", {}).get("project-key")
        self.name = data.get("plan", {}).get("name")

        for item in data.get("stages", []):
            # should be a single key dict
            assert len(item) == 1
            for stagename in item:
                stage = BamStage()
                stage.name = stagename
                stage.load(item[stagename])
                self.stages.append(stage)

        for stage in self.stages:
            for jobname in stage.jobs:
                job = BamJob()
                job.name = jobname
                assert jobname in data, f"no job named {jobname} !"
                job.load(data.get(job.name))
                self.jobs[job.name] = job
        self.repos = data.get("repositories", [])


class BamLoader(BaseLoader):
    """Load bamboo specs"""

    def __init__(self):
        self._config = {}
        self._loaded = []
        self._plans: List[BamPlan] = []

    def do_validate(self, baseobj) -> None:
        pass

    def get_jobs(self) -> List[str]:
        pass

    def get_job(self, name) -> dict:
        pass

    def load_job(self, name) -> BaseJob:
        pass

    def get_plans(self) -> List:
        return self._plans

    def get_stages(self) -> list:
        return []

    @property
    def config(self) -> dict:
        return self._config

    def load(self, filename):
        basename = os.path.basename(filename)
        if basename != BAMBOO_FILE:
            filename = os.path.join(filename, BAMBOO_FILE)

        with open(filename, "r") as data:
            loaded = yaml.load_all(data, Loader=get_stream_loader(filename))
            docs = [x for x in loaded]
            flat = []
            # flatten the above into a set of documents
            for item in docs:
                if isinstance(item, DocumentList):
                    subdocs = item.flatten()
                    flat.extend(subdocs)
                else:
                    flat.append(item)

            self._loaded = list(flat)

        # each document is a plan (a child pipeline)
        for plan in self._loaded:
            self.parse_plan(plan)

    def parse_plan(self, plandata: dict) -> None:
        plan = BamPlan()
        plan.load(plandata)
        if len(plan.jobs):  # only include plans that have jobs, ignore project settings documents
            self._plans.append(plan)

