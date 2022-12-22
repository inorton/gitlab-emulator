"""
Load a .gitlab-ci.yml file
"""
import os
import copy
import tempfile
from abc import ABC, abstractmethod
from typing import Dict, Any, Union, Optional, List
import requests

from .errors import ConfigLoaderError, BadSyntaxError, FeatureNotSupportedError
from .gitlab.types import RESERVED_TOP_KEYS, DEFAULT_JOB_KEYS
from .gitlab.urls import GITLAB_ORG_TEMPLATE_BASEURL
from .helpers import stringlist_if_string
from .jobs import NoSuchJob, Job
from .docker import DockerJob
from . import yamlloader
from .yamlloader import GitlabReference
from .userconfig import get_user_config_context
from gitlabemu.ruleparser import evaluate_rule
from .logmsg import warning, debugrule, fatal

DEFAULT_CI_FILE = ".gitlab-ci.yml"

DEFAULT_UNSUPPORTED_KEYWORDS = []
UNSUPPORTED_KEYWORDS = list(DEFAULT_UNSUPPORTED_KEYWORDS)


def check_unsupported(config: Dict[str, Any]) -> None:
    """
    Check of the configuration contains unsupported options, raise FeatureNotSupportedError on error
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


def do_single_include(baseobj: Dict[str, Any],
                      yamldir: str,
                      inc: Union[str, Dict[str, Any]],
                      handle_read=None,
                      variables: Optional[Dict[str, str]] = None,
                      filename: Optional[str] = None,
                      handle_fetch_project=None) -> Dict[str, Any]:
    """
    Load a single included file and return it's object graph
    :param handle_fetch_project: called to fetch an included file from another project
    :param filename: the name of the parent file wanting to include this one
    :param handle_read:
    :param baseobj: previously loaded and included objects
    :param yamldir: folder to search
    :param inc: file to read
    :param variables:
    :return:
    """
    supported_includes = ["local", "remote", "template", "project"]

    if variables is None:
        variables = {}
    if handle_read is None:
        handle_read = read
    location = None
    inc_type = None
    temp_content = None

    if isinstance(inc, str):
        location = inc.lstrip("/\\")
        inc_type = "local"
    elif isinstance(inc, dict):
        supported = False
        for inc_type in supported_includes:
            if inc_type in inc:
                supported = True
                break
        if not supported:
            raise FeatureNotSupportedError(f"Do not understand how to include {inc}")

        if "local" in inc:
            location = inc["local"]
            inc_type = "local"
        elif "remote" in inc:
            location = inc["remote"]
            inc_type = "remote"
        elif "template" in inc:
            location = inc["template"]
            inc_type = "template"
        elif "project" in inc:
            ref = inc.get("ref", "HEAD")
            location = f"{inc['project']}/{inc['file']}#{ref}".replace("//", "/")
            inc_type = "project"
            fatal(f"Not Yet Implemented, {inc}")

        rules = inc.get("rules", [])
        if not rules:
            debugrule(f"{filename} include: {inc}")
        else:
            matched_rules = False
            for rule in rules:
                # execute the rules, skip inclusion if none pass
                if_rule = rule.get("if", None)
                if if_rule:
                    matched = evaluate_rule(if_rule, dict(variables))
                    if matched:
                        debugrule(f"{filename} include '{inc}' matched {if_rule}")
                        matched_rules = True
                        break
            if not matched_rules:
                debugrule(f"{filename} not including: {inc}")
                return {}

    assert location, f"cannot work out include source location: {inc}"

    if location in baseobj["include"]:
        BadSyntaxError(f"{filename}: {location} has already been included")
    baseobj["include"].append(location)

    if inc_type == "local":
        if os.sep != "/":
            # pragma: linux no cover
            location = location.replace("/", os.sep)
        return handle_read(location, variables=False, validate_jobs=False, topdir=yamldir, baseobj=baseobj)
    elif inc_type == "template":
        # get the template from gitlab.com
        warning(f"Including gitlab.com template: {location}")
        inc_type = "remote"
        location = f"{GITLAB_ORG_TEMPLATE_BASEURL}/{location}"
    elif inc_type == "project":
        warning(f"Including CI yaml from another project: {location}")
        if not handle_fetch_project:
            warning("no project handler added")
        else:
            temp_content = handle_fetch_project(inc)

    if inc_type == "remote":
        # fetch the file, no authentication needed
        warning(f"Including remote CI yaml file: {location}")
        resp = requests.get(location, allow_redirects=True)
        if not resp.status_code == 200:
            raise ConfigLoaderError(f"HTTP error getting {location}: status {resp.status_code}")
        temp_content = resp.text

    if temp_content is not None:
        with tempfile.TemporaryDirectory() as temp_folder:
            path = os.path.join(str(temp_folder), "remote.yml")
            with open(path, "w") as fd:
                fd.write(temp_content)
            return handle_read(path, variables=False, validate_jobs=False, topdir=str(temp_folder), baseobj=baseobj)

    raise BadSyntaxError(f"Don't know how to include {inc}")


def do_includes(baseobj: Dict[str, Any],
                yamldir: str,
                incs: Union[str, List],
                handle_include=do_single_include,
                filename: Optional[str] = None) -> None:
    """
    Deep process include directives
    :param filename:
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
    #      rules:
    #        - if: $USE_SCRIPTS
    #    - local: "/templates/after.yaml"
    #    "/templates/windows-jobs.yaml"
    if incs:
        if isinstance(incs, list):
            includes = incs
        else:
            includes = [incs]
        for inc in includes:
            obj = handle_include(baseobj, yamldir, inc, filename=filename)
            for item in obj:
                if item != "include":
                    merge_dicts(baseobj, obj, item)


def strict_needs_stages() -> bool:
    """
    Return True if gitlab needs requires stage (gitlab 14.1 or earlier)
    :return:
    """
    ctx = get_user_config_context()
    version = ctx.gitlab.version
    if "." in version:
        major, minor = version.split(".", 1)
        if int(major) < 15:
            return int(minor) < 2
    return False


class ExtendsMixin:

    @staticmethod
    def do_single_extend_recursive(alljobs: dict, default_job: Dict[str, Any], name: str) -> Dict[str, Any]:
        """Do all the extends and !reference expansion for a single job"""
        assert name in alljobs
        unextended = alljobs.get(name)
        new_obj = copy.deepcopy(unextended)
        default_job = copy.deepcopy(default_job)
        if "variables" not in new_obj:
            new_obj["variables"] = {}
        pipeline_variables = alljobs.get("variables", {})

        base_jobs = stringlist_if_string(unextended.get("extends", []))
        if name in base_jobs:
            raise BadSyntaxError(f"Job '{name}' cannot extend itself")

        for base in base_jobs:
            if base not in alljobs:
                raise BadSyntaxError(f"Job '{name}' extends '{base}' which does not exist")
            if "extends" in alljobs[base]:
                baseobj = do_single_extend_recursive(dict(alljobs), default_job, base)
            else:
                baseobj = copy.deepcopy(alljobs[base])

            for keyname, value in baseobj.items():
                if isinstance(value, dict):
                    # this is a hash, merge the keys and values
                    if keyname not in new_obj or not isinstance(new_obj[keyname], dict):
                        # sometimes a string value can be replaced
                        # with a map, eg
                        #  image: imagename:latest  ->  image:
                        #                                 name: imagename:latest
                        new_obj[keyname] = {}
                    if keyname in unextended:
                        value.update(unextended[keyname])
                    new_obj[keyname].update(value)

                else:
                    # this is a scalar or list, copy it
                    if keyname not in unextended:
                        new_obj[keyname] = value

        # override any lists and values set in this map that were also pulled in via extends
        for override_key, override_value in unextended.items():
            if isinstance(override_value, dict):
                extended_value = new_obj.get(override_key, None)
                if isinstance(extended_value, dict):
                    # merge it
                    new_obj[override_key].update(override_value)
                else:
                    # replace it
                    new_obj[override_key] = override_value

        inherit_control = new_obj.get("inherit", {})
        inherit_variables = inherit_control.get("variables", list(pipeline_variables.keys()))
        inherit_default = inherit_control.get("default", list(default_job.keys()))

        if inherit_variables:  # can be False or a list
            inheritable_variables = {}
            for varname in inherit_variables:
                if varname in pipeline_variables:
                    inheritable_variables[varname] = pipeline_variables[varname]

            for varname, varvalue in inheritable_variables.items():
                if varname not in new_obj["variables"]:
                    new_obj["variables"][varname] = varvalue

        if inherit_default: # can be False or a list
            for valuekey in inherit_default:
                if valuekey not in new_obj:
                    if valuekey in default_job:
                        new_obj[valuekey] = copy.deepcopy(default_job[valuekey])

        return new_obj


    def do_extends(self, alljobs: Dict[str, Any]) -> None:
        """
        Process all the extends and !reference directives recursively
        :return:
        """
        default_image = alljobs.get("image", None)
        default_job = alljobs.get("default", None)
        default_services = alljobs.get("services", None)

        if not default_job:
            alljobs["default"] = {}
            if default_image:
                alljobs["default"]["image"] = default_image
                del alljobs["image"]
            if default_services:
                alljobs["default"]["services"] = default_services
                del alljobs["services"]
            default_job = alljobs["default"]

        jobnames = [x for x in alljobs.keys() if x not in RESERVED_TOP_KEYS] + ["default"]

        unextended = copy.deepcopy(alljobs)
        for name in jobnames:
            if name == "default":
                unexpected_keys = [x for x in alljobs["default"].keys() if x not in DEFAULT_JOB_KEYS]
                if unexpected_keys:
                    raise BadSyntaxError(f"default config contains unknown keys: {unexpected_keys}")
                continue
            new_job = self.do_single_extend_recursive(unextended, default_job, name)
            alljobs[name] = new_job

        # process !reference
        for name in alljobs:
            if name not in RESERVED_TOP_KEYS:
                variables = alljobs[name].get("variables", {})

                if isinstance(variables, GitlabReference):
                    ref: GitlabReference = variables
                    variables = dict(alljobs[ref.job].get(ref.element, {}))

                for varname in variables:
                    if isinstance(variables[varname], GitlabReference):
                        ref = variables[varname]
                        # get a variable from another job
                        if not ref.value:
                            raise BadSyntaxError("reference {} does not specify a variable name to copy".format(ref))
                        variables[varname] = alljobs[ref.job].get(ref.element, {})[ref.value]

                for varname in variables:
                    if isinstance(variables[varname], GitlabReference):
                        raise BadSyntaxError("Only one level of !reference is allowed")

                if name != "default":
                    alljobs[name]["variables"] = dict(variables)
                for scriptpart in ["before_script", "script", "after_script"]:
                    if scriptpart in alljobs[name]:
                        scriptlines = alljobs[name][scriptpart]
                        newlines = []
                        for line in scriptlines:
                            if isinstance(line, bool):
                                print(f"warning, line: {line} in job {name} evaluates to a yaml boolean, you probably want to quote \"true\" or \"false\"")
                                line = str(line).lower()
                            if isinstance(line, GitlabReference):
                                ref: GitlabReference = line
                                newlines.extend(alljobs[ref.job].get(ref.element, []))
                            else:
                                newlines.append(line)
                        # check for more than one level of nesting
                        for line in newlines:
                            if isinstance(line, GitlabReference):
                                raise BadSyntaxError("Only one level of !reference is allowed")
                        alljobs[name][scriptpart] = list(newlines)


def do_extends(alljobs: Dict[str, Any]) -> None:
    em = ExtendsMixin()
    return em.do_extends(alljobs)

def do_single_extend_recursive(alljobs: dict, default_job: Dict[str, Any], name: str) -> Dict[str, Any]:
    em = ExtendsMixin()
    return em.do_single_extend_recursive(alljobs, default_job, name)


def get_stages(config: Dict[str, Any]) -> List[str]:
    """
    Return a list of stages
    :param config:
    :return:
    """
    return config.get("stages", [".pre", "build", "test", "deploy", ".post"])


def get_jobs(config: Dict[str, Any]) -> List[str]:
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


def get_job(config: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    """
    Get the job dictionary
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


def job_docker_image(config: Dict[str, Any], name: str) -> Optional[Union[str, Dict[str, Any]]]:
    """
    Return a docker image if a job is configured for it
    :param config:
    :param name:
    :return:
    """
    if config.get("hide_docker"):
        return None
    return config[name].get("image")


class JobLoaderMixin:

    @staticmethod
    def load_job_ex(
            config: Dict[str, Any],
            name: str,
            allow_add_variables: Optional[bool] = True,
            configloader: Optional["BaseLoader"] = None,
    ) -> Union["Job", "DockerJob"]:
        """Load a job from a parsed pipeline configuration dictionary"""
        jobs = get_jobs(config)
        if name not in jobs:
            raise NoSuchJob(name)
        image = job_docker_image(config, name)
        if image:
            job = DockerJob()
        else:
            job = Job()
        job.configloader = configloader
        job.allow_add_variables = allow_add_variables
        job.load(name, config)

        return job

def load_job(config: Dict[str, Any],
             name: str,
             allow_add_variables: Optional[bool] = True,
             configloader: Optional["BaseLoader"] = None
             ) -> Union["Job", "DockerJob"]:
    """
    Load a job from the configuration
    :param allow_add_variables:
    :param configloader:
    :param config:
    :param name:
    :return:
    """
    jl = JobLoaderMixin()
    return jl.load_job_ex(config, name, allow_add_variables=allow_add_variables, configloader=configloader)


def compute_emulated_ci_vars(baseobj: Dict[str, Any]) -> Dict[str, Any]:
    if "variables" not in baseobj:
        baseobj["variables"] = {}

    workspace = baseobj.get(".gitlab-emulator-workspace", None)
    if workspace:
        folder = os.path.basename(workspace)
        baseobj["variables"]["CI_PROJECT_PATH"] = os.getenv(
            "CI_PROJECT_PATH", f"local/{folder}")
    baseobj["variables"]["CI_PIPELINE_ID"] = os.getenv(
        "CI_PIPELINE_ID", "0")
    baseobj["variables"]["CI_COMMIT_REF_SLUG"] = os.getenv(
        "CI_COMMIT_REF_SLUG", "offline-build")
    baseobj["variables"]["CI_COMMIT_SHA"] = os.getenv(
        "CI_COMMIT_SHA", "unknown")
    return baseobj


class VariablesMixin:

    @staticmethod
    def handle_variables(baseobj: Optional[Dict[str, Any]], yamlfile: str) -> Dict[str, Any]:
        baseobj = compute_emulated_ci_vars(baseobj)

        for name in os.environ:
            if name.startswith("CI_"):
                baseobj["variables"][name] = os.getenv(name, "")
        return compute_emulated_ci_vars(baseobj)

def do_variables(baseobj: Optional[Dict[str, Any]], yamlfile: str) -> Dict[str, Any]:
    # set CI_ values
    baseobj = compute_emulated_ci_vars(baseobj)
    vm = VariablesMixin()
    return vm.handle_variables(baseobj, yamlfile)



def merge_dicts(baseobj: dict, updated: dict, key: Any) -> None:
    if key in updated:
        newvalue = updated[key]
        if key in baseobj and isinstance(baseobj[key], dict) and isinstance(newvalue, dict):
            baseobj[key].update(newvalue)
        else:
            baseobj[key] = newvalue


class ValidatorMixin:

    @staticmethod
    def validate(config: Dict[str, Any]) -> None:
        """
        Validate the jobs in the loaded config map, raise a GitlabEmulatorError on error
        """
        jobs = get_jobs(config)
        stages = get_stages(config)

        for name in jobs:
            if name.startswith("."):
                continue

            job = get_job(config, name)

            # check that script is set
            if "trigger" not in job:
                if "script" not in job:
                    raise BadSyntaxError(f"Job '{name}' does not have a 'script' element.")

            # check that the stage exists
            if job["stage"] not in stages:
                raise ConfigLoaderError("job {} has stage {} does not exist".format(name, job["stage"]))

            # check needs
            needs = job.get("needs", [])
            for need in needs:
                # check the needed job exists
                if isinstance(need, dict):
                    need = need["job"]
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

def validate(config: Dict[str, Any]) -> None:
    vm = ValidatorMixin()
    vm.validate(config)


def read(
        yamlfile: str, *,
        variables=True,
        validate_jobs=True,
        topdir=None,
        baseobj=None,
        handle_include=do_includes,
        handle_extends=do_extends,
        handle_validate=validate,
        handle_variables=do_variables
         ) -> Dict[str, Any]:
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
        preloaded = yamlloader.ordered_load(yamlobj)
    with open(yamlfile, "r") as yamlobj:
        loaded = yamlloader.ordered_load(yamlobj, preloaded)

    if not baseobj:
        parent = True
        baseobj = {"include": []}

    for item in loaded:
        if item != "include":
            merge_dicts(baseobj, loaded, item)

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


class BaseLoader(ABC):
    def __init__(self):
        self.filename: Optional[str] = None
        self.rootdir: Optional[str] = None
        self.config: Dict[str, Any] = {
            ".gle-extra_variables": {}
        }
        self.included_files = []

        self._begun = False
        self._done = False
        self._current_file = None
        self._job_sources = {}
        self._job_classes = {}

    @property
    def variables(self) -> Dict[str, str]:
        found = {}
        found.update(self.config.get(".gle-extra_variables", {}))
        found.update(self.config.get("variables", {}))
        return found

    def add_variable(self, name: str, value: Optional[str] = None) -> None:
        """Add a pipeline variable"""
        if value is not None:
            self.config[".gle-extra_variables"][name] = value
        else:
            del self.config[".gle-extra_variables"][name]

    def get_docker_image(self, jobname: str) -> Optional[str]:
        """Get the docker image used by a job (if any)"""
        return job_docker_image(self.config, jobname)

    def get_jobs(self) -> List[str]:
        """
        Get the names of all jobs in the pipeline
        :return:
        """
        return get_jobs(self.config)

    def get_job(self, name: str) -> Dict[str, Any]:
        """
        Get a named job from the pipeline
        :param name:
        :return:
        """
        return get_job(self.config, name)

    def get_stages(self) -> List[str]:
        """
        Get the list of stages
        :return:
        """
        return get_stages(self.config)

    @abstractmethod
    def load(self, filename: str) -> None:
        pass

    @abstractmethod
    def load_job(self, name: str) -> Union["Job", "DockerJob"]:
        pass

    def get_job_filename(self, jobname: str) -> Optional[str]:
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


class Loader(BaseLoader, JobLoaderMixin, ValidatorMixin, ExtendsMixin):
    """
    A configuration loader for gitlab pipelines
    """

    def __init__(self, emulator_variables: Optional[bool] = True):
        super().__init__()
        self.create_emulator_variables = emulator_variables

    def load_job(self, name: str) -> Union["Job", "DockerJob"]:
        """Return a loaded job object"""
        job = self.load_job_ex(self.config, name,
                               allow_add_variables=self.create_emulator_variables,
                               configloader=self)
        return job

    def do_includes(self, baseobj: Dict[str, Any], yamldir: str, incs: Union[List, str]) -> None:
        """
        Process the list of include files
        :param baseobj:
        :param yamldir:
        :param incs:
        :return:
        """
        return do_includes(baseobj, yamldir, incs, handle_include=self.do_single_include, filename=self.filename)

    def do_single_include(self,
                          baseobj: Dict[str, Any],
                          yamldir: str,
                          inc: Union[str, Dict[str, Any]],
                          filename: str
                          ) -> Dict[str, Any]:
        """
        Include a single file and process it
        :param baseobj:
        :param yamldir:
        :param inc:
        :return:
        """
        return do_single_include(baseobj, yamldir, inc, handle_read=self._read, variables=self.variables, filename=filename)


    def do_validate(self, baseobj: Dict[str, Any]) -> None:
        """
        Validate the pipeline is defined legally
        :param baseobj:
        :return:
        """
        return self.validate(baseobj)

    def do_variables(self, baseobj: Dict[str, Any], yamlfile: Optional[str]) -> Dict[str, Any]:
        """
        Process the variables top level section
        :param baseobj:
        :param yamlfile:
        :return:
        """
        if "variables" not in baseobj:
            baseobj["variables"] = {}
        baseobj[".gitlab-emulator-workspace"] = os.path.abspath(os.path.dirname(yamlfile))
        if self.create_emulator_variables:
            return do_variables(baseobj, yamlfile)

    def _read(self,
              filename: Optional[str],
              baseobj: Optional[Dict[str, Any]] = None,
              **kwargs
              ) -> Dict[str, Any]:
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

        # collapse down list-of-lists in scripts
        for jobname in objdata:
            if not isinstance(objdata[jobname], dict):
                continue
            objdata[jobname]: Dict[str, Any]
            for script_name in ["before_script", "script", "after_script"]:
                if script_name not in objdata[jobname]:
                    continue
                objdata[jobname][script_name] = normalise_script(objdata[jobname][script_name])

        return objdata

    def load(self, filename: str) -> None:
        """
        Load a pipeline configuration from disk
        :param filename:
        :return:
        """
        assert not self._done, "load() called more than once"
        extra_vars = dict(self.config.get(".gle-extra_variables", {}))
        self.config = self._read(filename)
        self.config[".gle-extra_variables"] = dict(extra_vars)
        self._done = True


def normalise_script(script_item: Union[List[str], List[List[str]], str]) -> List[str]:
    """Convert scalar or 2d script lists into 1d lists"""
    if isinstance(script_item, str):
        return [script_item]
    # script is a list
    result = []
    for item in script_item:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result


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
