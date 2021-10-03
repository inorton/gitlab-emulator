"""
Load a .gitlab-ci.yml file
"""
import os
import re
from typing import Dict, Optional, List

import yaml

from .errors import GitlabEmulatorError
from .gitlab.types import RESERVED_TOP_KEYS
from .configtypes.job import ConfigJob
from .jobs import NoSuchJob, Job
from .docker import DockerJob
from . import yamlloader
from .userconfig import load_user_config, get_user_config_value

DEFAULT_CI_FILE = ".gitlab-ci.yml"

CURLY_NAME = re.compile(r"\${([A-Za-z0-9_]+)}")
SIMPLE_NAME = re.compile(r"\$([A-Za-z0-9_]+)")


class ConfigLoaderError(GitlabEmulatorError):
    """
    There was an error loading a gitlab configuration
    """
    pass


class BadSyntaxError(ConfigLoaderError):
    """
    The yaml was somehow invalid
    """

    def __init__(self, message):
        super(BadSyntaxError, self).__init__(message)


class FeatureNotSupportedError(ConfigLoaderError):
    """
    The loaded configuration contained gitlab features locallab does not
    yet support
    """

    def __init__(self, feature):
        self.feature = feature

    def __str__(self):
        return "FeatureNotSupportedError ({})".format(self.feature)


def check_unsupported(config):
    """
    Check of the configuration contains unsupported options
    :param config:
    :return:
    """
    for childname in config:
        # if this is a dict, it is probably a job
        child = config[childname]
        if isinstance(child, dict):
            for bad in ["parallel"]:
                if bad in config[childname]:
                    raise FeatureNotSupportedError(bad)


def strict_needs_stages() -> bool:
    """
    Return True if gitlab needs requires stage (gitlab 14.1 or earlier)
    :return:
    """
    cfg = load_user_config()
    version = str(get_user_config_value(cfg, "gitlab", name="version", default="14.2"))
    if "." in version:
        major, minor = version.split(".", 1)
        if int(major) < 15:
            return int(minor) < 2
    return False


def get_stages(config):
    """
    Return a list of stages
    :param config:
    :return:
    """
    return config.get("stages", [".pre", "build", "test", "deploy", ".post"])


def do_variables(baseobj, yamlfile):
    baseobj[".gitlab-emulator-workspace"] = os.path.abspath(os.path.dirname(yamlfile))
    if "variables" not in baseobj:
        baseobj["variables"] = {}
    # set CI_ values
    baseobj["variables"]["CI_PIPELINE_ID"] = os.getenv(
        "CI_PIPELINE_ID", "0")
    baseobj["variables"]["CI_COMMIT_REF_SLUG"] = os.getenv(
        "CI_COMMIT_REF_SLUG", "offline-build")
    baseobj["variables"]["CI_COMMIT_SHA"] = os.getenv(
        "CI_COMMIT_SHA", "unknown")
    for name in os.environ:
        if name.startswith("CI_"):
            baseobj["variables"][name] = os.environ[name]


class Loader(object):
    """
    A configuration loader for gitlab pipelines
    """

    def __init__(self):
        self.filename = None
        self.rootdir = None
        self.included_files = {}
        self._predefined = {}
        self._pipeline_defined = {}
        self._begun = False
        self._done = False
        self._job_sources = {}
        self._jobs = {}
        self._default_job = None

    def get_variable(self, name, predefined_only=False, default=None) -> Optional[str]:
        """
        Get the value of a variable, or a default
        :param default:
        :param name:
        :param predefined_only:
        :return:
        """
        value = self._predefined.get(name, default)
        if not predefined_only:
            value = self._pipeline_defined.get(name, value)
        return value

    def do_validate(self) -> bool:
        """
        Validate the pipeline is defined legally
        :param baseobj:
        :return:
        """
        return False

    def set_predefined_default(self, name, default_value):
        """
        Set a pre-defined pipeline variable
        :param name:
        :param default_value:
        :return:
        """
        self._predefined[name] = os.getenv(name, str(default_value))

    def set_variable(self, name, value):
        """
        Set a pipeline defined variable
        :return:
        """
        assert value is not None
        self._pipeline_defined[name] = str(value)

    def rule_test(self, rule: str, when: Optional[str] = None, predefined_only: Optional[bool] = False) -> bool:
        """
        Evaluate a rule against the pipeline variables
        :param when:
        :param rule:
        :param predefined_only:
        :return:
        """
        if when is None:
            when = "always"
        words = re.split(r"\s+", rule)
        if len(words) > 2:
            # glue the RHS back together
            lhs, operator, rhs = words[0], words[1], " ".join(words[2:])
            if self.test_expression(lhs, operator, rhs, predefined_only=predefined_only):
                return when

    def expand_variable(self, text, predefined_only=False) -> str:
        """
        Expand a ${NAME} or $NAME variable
        :param text:
        :param predefined_only:
        :return:
        """
        # search for ${NAME} variables
        for patt in [CURLY_NAME, SIMPLE_NAME]:
            found = patt.search(text)
            if found:
                # replace
                varname = found.group(1)
                value = self.get_variable(varname, default="", predefined_only=predefined_only)
                text = text.replace(found.group(0), value)
                break

        return text

    def test_expression(self, lhs, operator, rhs, predefined_only=False):
        """
        Evaluate a rule expression as True
        """
        rule_matched = False
        lhs = self.expand_variable(lhs, predefined_only=predefined_only)
        rhs = self.expand_variable(rhs, predefined_only=predefined_only)
        if operator == "==":
            rule_matched = lhs == rhs
        if operator == "!=":
            rule_matched = lhs != rhs
        if operator == "=~":
            rule_matched = re.search(rhs, lhs)
        return rule_matched

    def load(self, filename: str, predefined: Optional[Dict[str, str]] = None):
        """
        Load a pipeline configuration from disk
        :param filename: top level file to load
        :param predefined: a dict of env vars set before the pipeline is started
        :return:
        """
        assert not self._done, "load() called more than once"
        self._done = True
        if not predefined:
            self.set_predefined_default("CI_PIPELINE_ID", 0)
            self.set_predefined_default("CI_COMMIT_REF_SLUG", "offline-build")
            self.set_predefined_default("CI_COMMIT_SHA", "00" * 20)
            for name in os.environ:
                if name.startswith("CI_"):
                    self.set_predefined_default(name, os.environ[name])
        else:
            self._predefined = dict(predefined)
        self.add_file(filename)

    def can_include(self, entry) -> Optional[str]:
        """
        Process an `include` entry, if allowed, return the filename to include
        :param entry:
        :return:
        """
        if entry:
            if isinstance(entry, str):
                return entry
            if isinstance(entry, dict):
                if "project" in entry:
                    raise FeatureNotSupportedError("include: project: not yet supported")
                rules = entry.get("rules", [])
                if "local" not in entry:
                    raise ConfigLoaderError("include rule has no local key")
                if not rules:
                    return entry["local"]
                for rule in rules:
                    if "if" not in rule:
                        raise ConfigLoaderError("rule contains no if condition")
                    if self.rule_test(rule["if"], predefined_only=True):
                        return entry["local"]

    def add_file(self, filename, parent_filename: Optional[str] = None):
        """
        Include a file (depth first)
        :param filename:
        :param parent_filename: name of the file including this file
        :return:
        """
        if filename:
            if self.rootdir:
                filename = os.path.join(self.rootdir, filename)
            elif not self.rootdir:
                self.rootdir = os.path.dirname(os.path.abspath(filename))

            if filename in self.included_files:
                if self.included_files[filename] is None:
                    raise ConfigLoaderError(f"file {parent_filename} cannot include the top level CI file")
                raise ConfigLoaderError(f"file {filename} was already included from {self.included_files[filename]}")
            self.included_files[filename] = parent_filename
            with open(filename, "r") as datafile:
                data = yamlloader.ordered_load(datafile)
            includes = data.get("include", [])
            for item in includes:
                nextfile = self.can_include(item)
                self.add_file(nextfile, filename)

            # what jobs are defined in this current file
            file_jobs = [name for name in data.keys() if name not in RESERVED_TOP_KEYS]
            for name in file_jobs:
                if name in self._jobs:
                    raise ConfigLoaderError(f"Job {name} is redefined in {filename}")
                # create a job, everything that it extends should have been defined already
                job = ConfigJob(self, name, extends=data.get[name].get("extends", []))
                self._jobs[name] = job

            assert True

    def get_job_names(self) -> List[str]:
        """
        Get the list of jobs defined in the pipeline
        :return:
        """
        return []

    def get_job_filename(self, jobname: str) -> str:
        """
        Get the filename of for where the job is defined
        :param jobname:
        :return: job filename in unix format
        """
        jobfile = None
        for filename in self._job_sources:
            jobs = self._job_sources.get(filename)
            if jobname in jobs:
                jobfile = filename.replace("\\", "/")
                break
        return jobfile


def find_ci_config(path: str) -> Optional[str]:
    """
    Starting in path go upwards looking for a .gitlab-ci.yml file
    :param path:
    :return:
    """
    initdir = path
    path = os.path.abspath(path)
    while os.path.dirname(path) != path:
        filename = os.path.join(path, DEFAULT_CI_FILE)
        if os.path.exists(filename):
            return os.path.relpath(filename, initdir)
        path = os.path.dirname(path)
    return None
