"""
Load a .gitlab-ci.yml file
"""
import os
import copy
from collections import OrderedDict

import yaml

from .errors import GitlabEmulatorError
from .gitlab.types import RESERVED_TOP_KEYS
from .jobs import NoSuchJob, Job
from .docker import DockerJob
from . import yamlloader
from .userconfig import load_user_config, get_user_config_value

DEFAULT_CI_FILE = ".gitlab-ci.yml"

DEFAULT_UNSUPPORTED_KEYWORDS = []
UNSUPPORTED_KEYWORDS = list(DEFAULT_UNSUPPORTED_KEYWORDS)


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
            for bad in UNSUPPORTED_KEYWORDS:
                if bad in config[childname]:
                    raise FeatureNotSupportedError(bad)


def do_single_include(baseobj, yamldir, inc, handle_read=None):
    """
    Load a single included file and return it's object graph
    :param handle_read:
    :param baseobj: previously loaded and included objects
    :param yamldir: folder to search
    :param inc: file to read
    :return:
    """
    if handle_read is None:
        handle_read = read
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

    return handle_read(include, variables=False, validate_jobs=False, topdir=yamldir, baseobj=baseobj)


def do_includes(baseobj, yamldir, incs, handle_include=do_single_include):
    """
    Deep process include directives
    :param handle_include:
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
            obj = handle_include(baseobj, yamldir, filename)
            for item in obj:
                if item != "include":
                    baseobj[item] = obj[item]


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
            raise ConfigLoaderError("job {} has stage {} does not exist".format(name, job["stage"]))

        # check needs
        needs = job.get("needs", [])
        for need in needs:
            # check the needed job exists
            if need not in jobs:
                raise ConfigLoaderError("job {} needs job {} which does not exist".format(name, need))

            # check the needed job in in an earlier stage if running in <14.2 mode
            if strict_needs_stages():
                needed = get_job(config, need)
                stage_order = stages.index(job["stage"])
                need_stage_order = stages.index(needed["stage"])
                if not need_stage_order < stage_order:
                    raise ConfigLoaderError("job {} needs {} that is not in an earlier stage".format(name, need))

        if "artifacts" in job:
            if "paths" in job["artifacts"]:
                if not isinstance(job["artifacts"]["paths"], list):
                    raise ConfigLoaderError("artifacts->paths must be a list")
            if "reports" in job["artifacts"]:
                if not isinstance(job["artifacts"]["reports"], dict):
                    raise ConfigLoaderError("artifacts->reports must be a map")


def do_extends(alljobs: dict):
    """
    Process all the extends directives recursively
    :return:
    """
    default_image = alljobs.get("image", None)
    default_job = alljobs.get("default", None)
    default_services = alljobs.get("services", None)

    if not default_job:
        alljobs["default"] = {}
        if default_image:
            alljobs["image"] = default_image
            del alljobs["image"]
        if default_services:
            alljobs["services"] = default_services
            del alljobs["services"]

    jobnames = [x for x in alljobs.keys() if x not in RESERVED_TOP_KEYS] + ["default"]
    resolved = set()
    resolved.add("default")

    while len(resolved) < len(jobnames):
        for name in jobnames:
            if name not in resolved:
                if isinstance(alljobs[name], dict):
                    extends = alljobs[name].get("extends", ["default"])
                    if type(extends) == str:
                        bases = [extends]
                    else:
                        bases = extends

                    for basename in bases:
                        if basename not in jobnames:
                            raise BadSyntaxError("Job '{}' extends '{}' which does not exist".format(name, basename))

                    unresolved = set([base for base in bases if base not in resolved])
                    if unresolved:
                        # still need to resolve one of the bases, come back later..
                        continue

                    # do the extends work
                    new_obj = OrderedDict()
                    for base in bases + [name]:
                        baseobj = copy.deepcopy(alljobs[base])
                        for item in baseobj:
                            new_obj[item] = baseobj[item]
                    alljobs[name] = new_obj
                    resolved.add(name)


def get_stages(config):
    """
    Return a list of stages
    :param config:
    :return:
    """
    return config.get("stages", [".pre", "build", "test", "deploy", ".post"])


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
    return config[name].get("image")


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


def read(yamlfile, *, variables=True, validate_jobs=True, topdir=None, baseobj=None,
         handle_include=do_includes,
         handle_extends=do_extends,
         handle_validate=validate,
         handle_variables=do_variables
         ):
    """
    Read a .gitlab-ci.yml file into python types
    :param handle_variables:
    :param handle_validate:
    :param handle_extends:
    :param handle_include:
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

    handle_include(baseobj, topdir, loaded.get("include", []))
    baseobj["include"].append(yamlfile)

    if parent:
        # now do extends
        handle_extends(baseobj)

    check_unsupported(baseobj)

    if validate_jobs:
        if strict_needs_stages():
            if "stages" not in baseobj:
                baseobj["stages"] = ["test"]
        handle_validate(baseobj)

    if variables:
        handle_variables(baseobj, yamlfile)

    return baseobj


class Loader(object):
    """
    A configuration loader for gitlab pipelines
    """

    def __init__(self):
        self.filename = None
        self.rootdir = None

        self.config = {}
        self.included_files = []

        self._begun = False
        self._done = False
        self._current_file = None
        self._job_sources = {}
        self._job_classes = {}

    def get_docker_image(self, jobname):
        return job_docker_image(self.config, jobname)

    def do_includes(self, baseobj, yamldir, incs):
        """
        Process the list of include files
        :param baseobj:
        :param yamldir:
        :param incs:
        :return:
        """
        return do_includes(baseobj, yamldir, incs, handle_include=self.do_single_include)

    def do_single_include(self, baseobj, yamldir, inc):
        """
        Include a single file and process it
        :param baseobj:
        :param yamldir:
        :param inc:
        :return:
        """
        return do_single_include(baseobj, yamldir, inc, handle_read=self._read)

    def do_extends(self, baseobj):
        """
        Process all the defined extends directives in all loaded jobs
        :param baseobj:
        :return:
        """
        return do_extends(baseobj)

    def do_validate(self, baseobj):
        """
        Validate the pipeline is defined legally
        :param baseobj:
        :return:
        """
        return validate(baseobj)

    def do_variables(self, baseobj, yamlfile):
        """
        Process the variables top level section
        :param baseobj:
        :param yamlfile:
        :return:
        """
        return do_variables(baseobj, yamlfile)

    def get_jobs(self):
        """
        Get the names of all jobs in the pipeline
        :return:
        """
        return get_jobs(self.config)

    def get_job(self, name):
        """
        Get a named job from the pipeline
        :param name:
        :return:
        """
        return get_job(self.config, name)

    def get_stages(self):
        """
        Get the list of stages
        :return:
        """
        return get_stages(self.config)

    def _read(self, filename, baseobj=None, **kwargs):
        relative_filename = "unknown"
        if filename:
            self._current_file = filename
            # child triggered pipelines don't really have a file, so we should be parsing the real files here
            if not self.included_files:
                # first file
                filename = os.path.abspath(filename)
                self.rootdir = os.path.dirname(filename)
                self.filename = os.path.basename(filename)
                self._current_file = self.filename

            relative_filename = self._current_file
            self.included_files.append(relative_filename)

        if baseobj is None:
            before = {}
        else:
            before = dict(baseobj)

        objdata = read(filename, **kwargs,
                       baseobj=baseobj,
                       handle_include=self.do_includes,
                       handle_extends=self.do_extends,
                       handle_validate=self.do_validate,
                       handle_variables=self.do_variables,
                       )

        new_keys = (x for x in objdata if x not in before)
        new_keys = [x for x in new_keys if x not in RESERVED_TOP_KEYS]
        self._job_sources[relative_filename] = new_keys

        return objdata

    def load(self, filename):
        """
        Load a pipeline configuration from disk
        :param filename:
        :return:
        """
        assert not self._done, "load() called more than once"
        self.config = self._read(filename)
        self._done = True

    def get_job_filename(self, jobname):
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

def find_ci_config(path):
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
