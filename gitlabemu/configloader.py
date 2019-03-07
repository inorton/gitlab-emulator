"""
Load a .gitlab-ci.yml file
"""

import yaml
from .errors import GitlabEmulatorError


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

    if "services" in config:
        # might be able to support this with linking containers
        # https://docs.gitlab.com/ce/ci/docker/using_docker_images.html#how-services-are-linked-to-the-job
        raise FeatureNotSupportedError("services")

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
        loaded = yaml.load(yamlobj)

    check_unsupported(loaded)

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
