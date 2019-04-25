"""
Load a .gitlab-ci.yml file
"""
import os
import yaml
import subprocess

from .errors import GitlabEmulatorError
from .jobs import NoSuchJob, Job
from .docker import DockerJob


RESERVED_TOP_KEYS = ["stages",
                     "services",
                     "image",
                     "before_script",
                     "after_script",
                     "pages",
                     "variables",
                     "include",
                     ]


class ConfigLoaderError(GitlabEmulatorError):
    """
    There was an error loading a gitlab configuration
    """
    pass


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
    if "include" in config:
        raise FeatureNotSupportedError("include")

    for childname in config:
        # if this is a dict, it is probably a job
        child = config[childname]
        if isinstance(child, dict):
            for bad in ["extends", "parallel"]:
                if bad in config[childname]:
                    raise FeatureNotSupportedError(bad)


def read(yamlfile):
    """
    Read a .gitlab-ci.yml file into python types
    :param yamlfile:
    :return:
    """
    with open(yamlfile, "r") as yamlobj:
        loaded = yaml.load(yamlobj, Loader=yaml.FullLoader)

    check_unsupported(loaded)

    loaded["_workspace"] = os.path.abspath(os.path.dirname(yamlfile))

    if "variables" not in loaded:
        loaded["variables"] = {}

    # set CI_ values
    loaded["variables"]["CI_PIPELINE_ID"] = os.getenv(
        "CI_PIPELINE_ID", "0")
    loaded["variables"]["CI_COMMIT_REF_SLUG"] = os.getenv(
        "CI_COMMIT_REF_SLUG", "offline-build")
    loaded["variables"]["CI_COMMIT_SHA"] = os.getenv(
        "CI_COMMIT_SHA", "unknown")

    for name in os.environ:
        if name.startswith("CI_"):
            loaded["variables"][name] = os.environ[name]

    return loaded


def get_stages(config):
    """
    Return a list of stages
    :param config:
    :return:
    """
    return config.get("stages", ["test"])


def get_jobs(config):
    """
    Return a list of job names from the given configuration
    :param config:
    :return:
    """
    jobs = []
    for name in config:
        if name in RESERVED_TOP_KEYS:
            continue
        child = config[name]
        if isinstance(child, (dict,)):
            jobs.append(name)
    return jobs


def get_job(config, name):
    """
    Get the job
    :param config:
    :param name:
    :return:
    """
    assert name in get_jobs(config)

    return config.get(name)


def load_job(config, name):
    """
    Load a job from the configuration
    :param config:
    :param name:
    :return:
    """
    jobs = get_jobs(config)
    if name not in jobs:
        raise NoSuchJob(name)

    if config.get("image") or config[name].get("image"):
        job = DockerJob()
    else:
        job = Job()
    job.load(name, config)

    return job
