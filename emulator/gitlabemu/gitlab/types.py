"""
Classes for types in /api/v4/jobs/request

See https://gitlab.com/gitlab-org/gitlab-runner/-/blob/main/common/network.go for reference
"""
from typing import List, Optional

# pragma: no-cover
class GitlabType:
    """
    Base class for gitlab response types.
    """
    def from_dict(self, data):
        if data:
            for name in data:
                if hasattr(self, name):
                    setattr(self, name, data[name])


class JobInfo(GitlabType):
    """
    The job_info type
    """
    def __init__(self, data: dict):
        self.name = None
        self.stage = None
        self.project_id = None
        self.project_name = None
        self.from_dict(data)


class GitInfo(GitlabType):
    """
    The git_info type
    """
    def __init__(self, data: dict):
        self.repo_url = None
        self.ref = None
        self.sha = None
        self.before_sha = None
        self.ref_type = None
        self.refspecs = None
        self.depth = None
        self.from_dict(data)


class RunnerInfo(GitlabType):
    """
    The runner_info type
    """
    def __init__(self, data: dict):
        self.timeout = 0
        self.from_dict(data)


class JobVariables(GitlabType):
    """
    The variables type
    """
    def __init__(self, data: Optional[List] = None):
        self.vars = {}
        self.public_vars = set()
        self.from_list(data)

    def from_list(self, data):
        if data:
            for item in data:
                name = item["key"]
                value = item["value"]
                public = item["public"]
                self.vars[name] = str(value)
                if public:
                    self.public_vars.add(name)


class Step(GitlabType):
    def __init__(self, data: Optional[dict] = None):
        self.name = None
        self.script = []
        self.timeout = 0
        self.when = "always"
        self.allow_failure = False
        self.from_dict(data)


class Image(GitlabType):
    def __init__(self, data: Optional[dict] = None):
        self.name = None
        self.alias = None
        self.command = []
        self.entrypoint = []
        self.ports = []
        if data:
            self.from_dict(data)

    @classmethod
    def from_value(cls, value):
        result = None
        if value:
            result = Image()
            if isinstance(value, dict):
                result.from_dict(value)
            if isinstance(value, str):
                result.name = value
        return result


class Artifact(GitlabType):
    def __init__(self, data: dict):
        self.name = None
        self.untracked = False
        self.paths = []
        self.exclude = []
        self.when = "on_success"
        self.artifact_type = None
        self.artifact_format = "zip"
        self.expire_in = None
        self.from_dict(data)


class Dependency(GitlabType):
    def __init__(self, data: dict):
        self.id = 0
        self.token = None
        self.name = None
        self.artifacts_file = {}
        self.from_dict(data)


class JobResponse:
    """
    The response to polling for a new job
    """
    def __init__(self, data: dict):
        self.id = data.get("id", 0)
        self.token = data.get("token", None)
        self.allow_git_fetch = data.get("allow_git_fetch", False)
        self.job_info = JobInfo(data.get("job_info", {}))
        self.runner_info = RunnerInfo(data.get("runner_info", {}))
        self.variables = [RunnerInfo(x) for x in data.get("variables", [])]
        self.steps = [Step(x) for x in data.get("steps", [])]
        self.image = data.get("image", None)
        self.services = [Image(x) for x in data.get("services", [])]
        self.artifacts = [Artifact(x) for x in data.get("artifacts", [])]
        self.dependencies = [Dependency(x) for x in data.get("dependencies", [])]


class IncludeFile(GitlabType):
    """
    Represent an include directive
    """
    def __init__(self):
        self.local = None
        self.file = None
        self.remote = None
        self.template = None
        self.rules = []

    @classmethod
    def from_value(cls, value):
        result = None
        if value:
            result = cls()
            if isinstance(value, dict):
                result.from_dict(value)
            if isinstance(value, str):
                result.local = value

        return result


RESERVED_TOP_KEYS = ["stages",
                     "services",
                     "image",
                     "cache",
                     "before_script",
                     "after_script",
                     "pages",
                     "variables",
                     "include",
                     "workflow",
                     "default",
                     ".gitlab-emulator-workspace"
                     ]

DEFAULT_JOB_KEYS = [
    "after_script",
    "artifacts",
    "before_script",
    "cache",
    "image",
    "interruptible",
    "retry",
    "services",
    "tags",
    "timeout",
]