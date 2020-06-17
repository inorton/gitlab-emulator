"""
Load a .gitlab-ci.yml file
"""
import os
import sys
import yaml

from .errors import GitlabEmulatorError
from .jobs import NoSuchJob, Job
from .docker import DockerJob
from . import yamlloader

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


def do_single_include(yamldir, inc):
    """
    Load a single included file and return it's object graph
    :param yamldir: folder to search
    :param inc: file to read
    :return:
    """
    include = None
    if isinstance(inc, str):
        include = inc
    elif isinstance(inc, dict):
        include = inc.get("local", None)
        if not include:
            raise FeatureNotSupportedError("We only support local includes right now")

    include = include.lstrip("/\\")
    # make this work on windows
    if os.sep != "/":
        include = include.replace("/", os.sep)

    include = os.path.join(yamldir, include)

    return read(include, variables=False)


def do_includes(baseobj, yamldir):
    """
    Deep process include directives
    :param baseobj:
    :param yamldir: load include files relative to here
    :return:
    """
    # include can be an array or a map.
    #
    # include: "/templates/scripts.yaml"
    #
    # include:
    #   - "/templates/scripts.yaml"
    #   - "/templates/windows-jobs.yaml"
    #
    # include:
    #   local: "/templates/scripts.yaml"
    #
    # include:
    #    - local: "/templates/scripts.yaml"
    #    - local: "/templates/after.yaml"
    #    "/templates/windows-jobs.yaml"
    incs = baseobj.get("include", None)
    if incs:
        if isinstance(incs, list):
            includes = incs
        else:
            includes = [incs]
        for filename in includes:
            obj = do_single_include(yamldir, filename)
            for item in obj:
                if item in baseobj:
                    print("warning, {} is already defined in the loaded yaml".format(item))
                baseobj[item] = obj[item]

    # now do extends
    for job in baseobj:
        if isinstance(baseobj[job], dict):
            extends = baseobj[job].get("extends", None)
            if extends:
                baseclass = baseobj.get(extends, None)
                if not baseclass:
                    raise BadSyntaxError("job {} extends {} which cannot be found".format(job, extends))
                copy = dict(baseobj[job])
                newbase = dict(baseclass)
                for item in copy:
                    newbase[item] = copy[item]
                baseobj[job] = newbase


def read(yamlfile, check_supported=True, variables=True):
    """
    Read a .gitlab-ci.yml file into python types
    :param yamlfile:
    :return:
    """
    with open(yamlfile, "r") as yamlobj:
        loaded = yamlloader.ordered_load(yamlobj, Loader=yaml.FullLoader)

    if check_supported:
        check_unsupported(loaded)

    do_includes(loaded, os.path.dirname(yamlfile))

    if variables:
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


def job_docker_image(config, name):
    """
    Return a docker image if a job is configured for it
    :param config:
    :param name:
    :return:
    """
    if config.get("hide_docker"):
        return None
    image = config[name].get("image")
    if not image:
        image = config.get("image")
    return image


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
    image = job_docker_image(config, name)
    if image:
        job = DockerJob()
    else:
        job = Job()

    job.load(name, config)

    return job
