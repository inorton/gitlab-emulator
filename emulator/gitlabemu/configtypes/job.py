"""
Represent jobs loaded from yaml
"""
from typing import Optional, List


class ConfigJob:
    def __init__(self, loader, name, extends: Optional[List[str]] = None):
        if extends is None:
            extends = []
        self.loader = loader
        self.name = name
        self.extends = list(extends)
        self.rules = []
        self.when = None
        self.stage = None
        self.image = None
        self.variables = {}
        self.before_script = []
        self.script = []
        self.after_script = []
        self.needs = []
        self.artifacts = []
        self.services = []


