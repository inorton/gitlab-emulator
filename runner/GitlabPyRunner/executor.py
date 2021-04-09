"""
Call gitlab-emulator's code to execute a job
"""
import sys
import glob
import os
import shutil
import tempfile
import subprocess
import time
import stat
import traceback

import requests
import zipfile

import yaml

from .common import gethostname, iswindows, generate_config, begin_log_section, end_log_section
from .trace import TraceProxy
from .consts import NAME, VERSION
from unidecode import unidecode


def get_variable(job, *names, default=None):
    """
    Get a named variable from a job
    :param job:
    :param name:
    :param default:
    :return:
    """
    for var in job["variables"]:
        for name in names:
            if var["key"] == name:
                return var["value"]
    return default


def archive(trace, config, jobname, tempdir, build_folder, success):
    """
    Create a zip archive of the build artifacts if required
    :param trace: trace proxy
    :param config: global gitlab config data
    :param jobname: the job name
    :param tempdir: the temporary data folder
    :param build_folder: the root folder of this build
    :param success: True for successful builds
    :return:
    """
    # handle artifact upload
    job_config = config[jobname]
    if "artifacts" in job_config:
        when = "on_success"  # default
        if "when" in job_config["artifacts"]:
            when = job_config["artifacts"]["when"]

        if when != "always":
            if when == "on_success" and not success:
                return None
            if when == "on_failure" and success:
                return None

        if "paths" not in job_config["artifacts"]:
            return None

        excludes = []
        excludepatts = job_config["artifacts"].get("exclude", [])
        for item in excludepatts:
            if os.sep != '/':
                item = item.replace("/", os.sep)
            excludepatt = os.path.join(build_folder, item)
            excludes.extend(glob.glob(excludepatt, recursive=True))

        trace.writeline("\nFinding artifacts...")
        if excludes:
            trace.writeline("\nExclude {} artifacts".format(len(excludes)))

        paths = job_config["artifacts"]["paths"]
        zipname = "archive.zip"
        if "name" in job_config["artifacts"]:
            # TODO expand variables for this
            zipname = job_config["artifacts"]["name"] + ".zip"

        zippath = os.path.join(tempdir, zipname)
        with zipfile.ZipFile(zippath, "w") as zipobj:
            for item in paths:
                trace.writeline(".. finding {}".format(item))
                # patterns are posix paths and globs, convert them to local on windows
                if os.sep != '/':
                    item = item.replace("/", os.sep)
                localpatt = os.path.join(build_folder, item)
                matches = glob.glob(localpatt, recursive=True)

                for include in matches:
                    if include in excludes:
                        continue
                    relpath = os.path.relpath(include, build_folder)
                    if os.path.isfile(include):
                        trace.writeline(".. match {}".format(include))
                        zipobj.write(include, relpath)
                    if os.path.isdir(include):
                        # recurse adding the whole folder
                        for root, _, files in os.walk(include):
                            for file in files:
                                fname = os.path.join(root, file)
                                relname = os.path.relpath(fname, build_folder)
                                trace.writeline(".. match {}".format(relname))
                                zipobj.write(fname, relname)
        return zippath
    return None


def clean(trace, folder, docker, attempts=10):
    """
    Totally delete the given folder regardless of permissions inside
    :param trace:
    :param folder:
    :param docker:
    :param attempts: retry this many times
    :return:
    """
    from gitlabemu import logmsg

    logmsg.info("Cleaning build {}".format(folder))
    # make everything deletable on windows
    if iswindows():
        for root, dirs, files in os.walk(folder):
            for item in files + dirs:
                path = os.path.join(root, item)
                if not os.access(path, os.W_OK):
                    # shutil.rmtree() will barf on ro files
                    os.chmod(path, stat.S_IWUSR)
                    # so lets delete it now
                    os.unlink(path)
    try:
        try:
            shutil.rmtree(folder)
        except:
            # failed, if we have docker, try to use that
            if docker:
                from gitlabemu import logmsg
                if iswindows():
                    logmsg.fatal("unable to clean {}".format(folder))
                else:
                    # try to use a busybox
                    parent = os.path.abspath(os.path.dirname(folder))
                    foldername = os.path.basename(folder)
                    subprocess.check_call(
                        ["docker", "run", "--rm",
                         "-w", parent,
                         "-v", parent + ":" + parent,
                         "busybox:latest",
                         "rm", "-rf", foldername
                         ])
                    return
            raise
    except Exception as err:
        # possibly this is windows virus scanning?
        if attempts > 0:
            trace.writeline("clean failed.. sleeping ".format(err, attempts))
            time.sleep(3 * (4 - attempts))
            clean(trace, folder, docker, attempts - 1)
        else:
            trace.writeline("Error cleaning after build {}".format(err))
            raise
    finally:
        trace.flush()


def trace_checkoutput(trace, cmdline, cwd):
    """
    Run a program and emit the trace
    :param cmdline:
    :param cwd:
    :return:
    """
    try:
        trace.write(subprocess.check_output(cmdline, cwd=cwd, stderr=subprocess.STDOUT))
    except subprocess.CalledProcessError as cpe:
        trace.writeline("Error running {}".format(cmdline))
        trace.write(cpe.output)
        raise


def run(runner, job, docker):
    """
    Execute the given job here using gitlab-emulator
    :param runner: the runner object
    :param job: the job response from the server
    :param docker: if True, we can use docker for housekeeping
    :return:
    """
    from gitlabemu import logmsg, configloader, errors

    trace = TraceProxy(runner, job)

    logmsg.FATAL_EXIT = False

    trace.writeline("Running on {} {} {}".format(gethostname(), NAME, VERSION))
    if docker:
        trace.writeline("Using Docker executor")
    else:
        trace.writeline("Using shell executor")

    tempdir = tempfile.mkdtemp(dir=runner.builds)
    build_dir = os.path.join(tempdir, get_variable(job, "CI_PROJECT_PATH"))
    build_dir_abs = os.path.abspath(build_dir)
    try:
        os.makedirs(build_dir)

        # clone the git repo defined in the job
        git = job["git_info"]

        begin_log_section(trace, "git", "Source Control")

        trace.writeline("Cloning project..")
        trace_checkoutput(trace, ["git", "clone", git["repo_url"], build_dir], cwd=tempdir)

        # checkout the ref to build
        trace_checkoutput(trace, ["git", "checkout", "-f", get_variable(job, "CI_COMMIT_SHA", "CI_COMMIT_REF")], cwd=build_dir_abs)

        end_log_section(trace, "git")

        # config_file
        jobname = job["job_info"]["name"]
        config, derived_config = load_pipeline_config(trace, tempdir, build_dir_abs, job, jobname)

        if derived_config:
            trace.writeline("Dervied work folder is {}".format(build_dir_abs))


        # populate real vars
        for var in job["variables"]:
            # support 'file' variables
            if 'file' in var.keys() and var["file"]:
                filevar = tempfile.NamedTemporaryFile(dir=tempdir, delete=False )
                filevar.write( str.encode(var["value"]))
                name = var["key"]
                config["variables"][name] = filevar.name
                filevar.close()
            else:
                # fix 'None' values
                if var["value"] is None:
                    var["value"] = ""
                name = var["key"]
                config["variables"][name] = unidecode(var["value"])

        emulator_job = configloader.load_job(config, jobname)
        trace.emulator_job = emulator_job

        runner.get_dependencies(trace, job, build_dir_abs)

        emulator_job.stdout = trace

        success = False
        error = False

        try:
            emulator_job.run()
            success = True
        except errors.GitlabEmulatorError:
            # the job failed
            try:
                emulator_job.abort()
            except OSError:
                pass
        except requests.HTTPError:
            error = True
            emulator_job.abort()

        if not error:  # success or failure but not some internal errors
            archive_file = archive(trace, config, jobname, tempdir, build_dir_abs, success)
            if archive_file:
                runner.upload(trace, job, archive_file)

        trace.writeline("Job complete success={}".format(success))
        return success
    except Exception as err:
        trace.writeline("Runner error: {}".format(err))
        error_type, error, tb = sys.exc_info()
        stacks = traceback.format_tb(tb)
        for x in stacks:
            trace.writeline(x)

    finally:
        clean(trace, tempdir, docker)


def load_pipeline_config(trace, tempdir, build_dir_abs, job, jobname):
    from gitlabemu import configloader
    loader = configloader.Loader()
    derived = False
    ci_cfg = get_variable(job, "CI_CONFIG_PATH")
    if ci_cfg:
        ci_file = os.path.join(build_dir_abs, ci_cfg)
    if os.path.exists(ci_file):
        loader.load(ci_file)

    config = loader.config

    if not ci_cfg or jobname not in loader.get_jobs():
        begin_log_section(trace, "child-job", "Execute child job")
        trace.writeline("Warning: CI_CONFIG_PATH is empty or unset")
        trace.writeline("Warning: gitlab-python-runner child-pipeline support is experimental")
        trace.writeline("Computing child job steps..")

        new_config = generate_config(job)
        ci_cfg = os.path.join(tempdir, "child-job.yml")
        with(open(ci_cfg, "w")) as new_config_fh:
            yaml.safe_dump(new_config, stream=new_config_fh)
        with(open(ci_cfg, "r")) as new_config_fh:
            for line in new_config_fh:
                trace.writeline("#" + line)
        end_log_section(trace, "child-job")
        config = configloader.read(ci_cfg, topdir=build_dir_abs)
        config["variables"]["CI_PROJECT_DIR"] = build_dir_abs
        config[".gitlab-emulator-workspace"] = build_dir_abs

        derived = True

    return config, derived
