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


def do_single_include(baseobj, yamldir, inc):
    """
    Load a single included file and return it's object graph
    :param baseobj: previously loaded and included objects
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

    if include in baseobj["include"]:
        BadSyntaxError("The file {} has already been included".format(include))
    baseobj["include"].append(include)

    # make this work on windows
    if os.sep != "/":
        include = include.replace("/", os.sep)

    print("include : {}".format(include), file=sys.stderr)

    return read(include, variables=False, validate_jobs=False, topdir=yamldir, baseobj=baseobj)


def do_includes(baseobj, yamldir, incs):
    """
    Deep process include directives
    :param baseobj:
    :param yamldir: load include files relative to here
    :param incs: files to load
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
    if incs:
        if isinstance(incs, list):
            includes = incs
        else:
            includes = [incs]
        for filename in includes:
            obj = do_single_include(baseobj, yamldir, filename)
            for item in obj:
                if item != "include":
                    baseobj[item] = obj[item]


def validate(config):
    """
    Validate the jobs in the loaded config map
    """
    jobs = get_jobs(config)
    stages = get_stages(config)

    for name in jobs:
        if name.startswith("."):
            continue

        job = get_job(config, name)

        # check that the stage exists
        if job["stage"] not in stages:
            raise ConfigLoaderError("job {} stage {} does not exist".format(name, job["stage"]))

        # check needs
        needs = job.get("needs", [])
        for need in needs:
            # check the needed job exists
            if need not in jobs:
                raise ConfigLoaderError("job {} needs job {} which does not exist".format(name, need))

            # check the needed job in in an earlier stage
            needed = get_job(config, need)
            stage_order = stages.index(job["stage"])
            need_stage_order = stages.index(needed["stage"])
            if not need_stage_order < stage_order:
                raise ConfigLoaderError("job {} needs {} that is not in an earlier stage".format(name, need))


def read(yamlfile, variables=True, validate_jobs=True, topdir=None, baseobj=None):
    """
    Read a .gitlab-ci.yml file into python types
    :param yamlfile:
    :param validate_jobs: if True, reject jobs with bad configuration (yet valid yaml)
    :param variables: if True, inject a variables map (valid for top level only)
    :param topdir: the root directory to search for include files
    :param baseobj: the document tree loaded so far.
    :return:
    """
    parent = False
    if topdir is None:
        topdir = os.path.dirname(yamlfile)
        print("setting topdir={}".format(topdir), file=sys.stderr)
    else:
        yamlfile = os.path.join(topdir, yamlfile)
    with open(yamlfile, "r") as yamlobj:
        loaded = yamlloader.ordered_load(yamlobj, Loader=yaml.FullLoader)

    if not baseobj:
        parent = True
        baseobj = {"include": []}

    for item in loaded:
        if item != "include":
            baseobj[item] = loaded[item]

    do_includes(baseobj, topdir, loaded.get("include", []))
    baseobj["include"].append(yamlfile)

    if parent:
        # now do extends
        for job in baseobj:
            if isinstance(baseobj[job], dict):
                extends = baseobj[job].get("extends", None)
                if extends is not None:
                    if type(extends) == str:
                        bases = [extends]
                    else:
                        bases = extends
                    for basename in bases:
                        baseclass = baseobj.get(basename, None)
                        if not baseclass:
                            raise BadSyntaxError("job {} extends {} which cannot be found".format(job, basename))
                        copy = dict(baseobj[job])
                        newbase = dict(baseclass)
                        for item in copy:
                            newbase[item] = copy[item]
                        baseobj[job] = newbase

    check_unsupported(baseobj)

    if validate_jobs:
        if "stages" not in baseobj:
            baseobj["stages"] = ["test"]
        validate(baseobj)

    if variables:
        baseobj["_workspace"] = os.path.abspath(os.path.dirname(yamlfile))
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

    return baseobj


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

    job = config.get(name)

    # set some implied defaults
    if "stage" not in job:
        job["stage"] = "test"

    return job


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
