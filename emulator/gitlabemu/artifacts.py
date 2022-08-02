"""Represent job artifacts and reports"""
from .errors import BadSyntaxError


class GitlabArtifacts:
    def __init__(self):
        self.name = None
        self.public = False
        self.untracked = False
        self.when = "on_success"
        self.paths = []
        self.exclude = []
        self.reports = {}

    def load(self, data: dict):
        self.paths = data.get("paths", [])
        self.exclude = data.get("exclude", [])
        self.name = data.get("name", self.name)
        self.public = data.get("public", self.public)
        self.untracked = data.get("untracked", self.untracked)
        self.reports = data.get("reports", {})
        self.when = data.get("when", self.when)

        if isinstance(self.reports.get("junit", []), str):
            # is a string, canonicalize as a list
            self.reports["junit"] = [self.reports["junit"]]

        if not isinstance(self.paths, list):
            raise BadSyntaxError(f"artifacts:paths must be a list of paths, got {self.paths} ({type(self.paths)} instead)")

