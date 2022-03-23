import re
import sys
import os
import argparse
import zipfile
from typing import Optional, List

from gitlab.v4.objects import ProjectPipeline, ProjectPipelineJob

from . import configloader
from . import stream_response
from .docker import has_docker
from .localfiles import restore_path_ownership
from .helpers import is_apple, is_linux, is_windows, git_worktree
from .userconfig import load_user_config, get_user_config_value, override_user_config_value, USER_CFG_ENV

from gitlab import Gitlab

CONFIG_DEFAULT = ".gitlab-ci.yml"

parser = argparse.ArgumentParser(prog="{} -m gitlabemu".format(os.path.basename(sys.executable)))
parser.add_argument("--list", "-l", dest="LIST", default=False,
                    action="store_true",
                    help="List runnable jobs")
parser.add_argument("--hidden", default=False, action="store_true",
                    help="Show hidden jobs in --list(those that start with '.')")
parser.add_argument("--full", "-r", dest="FULL", default=False,
                    action="store_true",
                    help="Run any jobs that are dependencies")
parser.add_argument("--config", "-c", dest="CONFIG", default=CONFIG_DEFAULT,
                    type=str,
                    help="Use an alternative gitlab yaml file")
parser.add_argument("--settings", "-s", dest="USER_SETTINGS", type=str, default=None,
                    help="Load gitlab emulator settings from a file")
parser.add_argument("--chdir", "-C", dest="chdir", default=None, type=str, metavar="DIR",
                    help="Change to this directory before running")
parser.add_argument("--enter", "-i", dest="enter_shell", default=False, action="store_true",
                    help="Run an interactive shell but do not run the build"
                    )
parser.add_argument("--before-script", "-b", dest="before_script_enter_shell", default=False, action="store_true",
                    help="Run the 'before_script' commands before entering the shell"
                    )
parser.add_argument("--user", "-u", dest="shell_is_user", default=False, action="store_true",
                    help="Run the interactive shell as the current user instead of root")

parser.add_argument("--cmd", default=False, action="store_true", dest="cmd_shell",
                    help="Force use of legacy cmd.exe instead of powershell on windows")

parser.add_argument("--shell-on-error", "-e", dest="error_shell", type=str,
                    help="If a docker job fails, execute this process (can be a shell)")

parser.add_argument("--ignore-docker", dest="no_docker", action="store_true", default=False,
                    help="If set, run jobs using the local system as a shell job instead of docker"
                    )

parser.add_argument("--var", dest="var", type=str, default=[], action="append",
                    help="Set a pipeline variable, eg DEBUG or DEBUG=1")

parser.add_argument("--revar", dest="revars", metavar="REGEX", type=str, default=[], action="append",
                    help="Set pipeline variables that match the given regex")

parser.add_argument("--parallel", type=str,
                    help="Run JOB as one part of a parallel axis (eg 2/4 runs job 2 in a 4 parallel matrix)")

parser.add_argument("--from", type=str, dest="FROM",
                    metavar="SERVER/PROJECT/PIPELINE",
                    help="Fetch needed artifacts for the current job from the given pipeline, eg nc/321/41881")

parser.add_argument("--download", default=False, action="store_true",
                    help="Instead of building JOB, download the artifacts of JOB from gitlab (requires --from)")

parser.add_argument("--insecure", "-k", dest="insecure", default=False, action="store_true",
                    help="Ignore TLS certificate errors when fetching from remote servers")

parser.add_argument("JOB", type=str, default=None,
                    nargs="?",
                    help="Run this named job")

def die(msg):
    """print an error and exit"""
    print("error: " + str(msg), file=sys.stderr)
    sys.exit(1)


def apply_user_config(loader: configloader.Loader, cfg: dict, is_docker: bool):
    """
    Add the user config values to the loader
    :param loader:
    :param cfg:
    :param is_docker:
    :return:
    """
    allvars = get_user_config_value(cfg, "variables", default={})
    for name in allvars:
        loader.config["variables"][name] = allvars[name]

    if is_docker:
        jobvars = get_user_config_value(cfg, "docker", name="variables", default={})
    else:
        jobvars = get_user_config_value(cfg, "local", name="variables", default={})

    for name in jobvars:
        loader.config["variables"][name] = jobvars[name]


def execute_job(config, jobname, seen=None, recurse=False):
    """
    Run a job, optionally run required dependencies
    :param config: the config dictionary
    :param jobname: the job to start
    :param seen: completed jobs are added to this set
    :param recurse: if True, execute in dependency order
    :return:
    """
    if seen is None:
        seen = set()
    if jobname not in seen:
        jobobj = configloader.load_job(config, jobname)
        if recurse:
            for need in jobobj.dependencies:
                execute_job(config, need, seen=seen, recurse=True)
        jobobj.run()
        seen.add(jobname)


def gitlab_api(cfg: dict, alias: str, secure=True) -> Gitlab:
    """Create a Gitlab API client"""
    servers = get_user_config_value(cfg, "gitlab", name="servers", default=[])
    for item in servers:
        if item.get("name") == alias:
            server = item.get("server")
            token = item.get("token")
            if not server:
                die(f"no server address for alias {alias}")
            if not token:
                die(f"no api-token for alias {alias} ({server})")
            client = Gitlab(url=server, private_token=token, ssl_verify=secure)

            return client

    die(f"Cannot find local configuration for server {alias}")


def run(args=None):
    options = parser.parse_args(args)
    loader = configloader.Loader()
    yamlfile = options.CONFIG
    jobname = options.JOB

    if options.chdir:
        if not os.path.exists(options.chdir):
            die(f"Cannot change to {options.chdir}, no such directory")
        os.chdir(options.chdir)

    if not os.path.exists(yamlfile):
        print(f"{configloader.DEFAULT_CI_FILE} not found.", file=sys.stderr)
        find = configloader.find_ci_config(os.getcwd())
        if find:
            topdir = os.path.abspath(os.path.dirname(find))
            print(f"Found config: {find}", file=sys.stderr)
            die(f"Please re-run from {topdir}")
        sys.exit(1)

    if options.USER_SETTINGS:
        os.environ[USER_CFG_ENV] = options.USER_SETTINGS

    cfg = load_user_config()
    try:
        fullpath = os.path.abspath(yamlfile)
        rootdir = os.path.dirname(fullpath)
        os.chdir(rootdir)
        loader.load(fullpath)
    except configloader.ConfigLoaderError as err:
        die("Config error: " + str(err))

    options.cmd_shell = get_user_config_value(cfg, "windows", name="cmd", default=options.cmd_shell)
    if options.cmd_shell:
        loader.config[".gitlabemu-windows-shell"] = "cmd.exe"

    hide_dot_jobs = not options.hidden

    if options.FULL and options.parallel:
        die("--full and --parallel cannot be used together")

    if options.LIST:
        for jobname in sorted(loader.get_jobs()):
            if jobname.startswith(".") and hide_dot_jobs:
                continue
            print(jobname)
    elif not jobname:
        parser.print_usage()
        sys.exit(1)
    else:
        jobs = sorted(loader.get_jobs())
        if jobname not in jobs:
            die(f"No such job {jobname}")

        if options.parallel:
            if loader.config[jobname].get("parallel", None) is None:
                die(f"Job {jobname} is not a parallel enabled job")

            pindex, ptotal = options.parallel.split("/", 1)
            pindex = int(pindex)
            ptotal = int(ptotal)
            if pindex < 1:
                die("CI_NODE_INDEX must be > 0")
            if ptotal < 1:
                die("CI_NODE_TOTAL must be > 1")
            if pindex > ptotal:
                die("CI_NODE_INDEX must be <= CI_NODE_TOTAL, (got {}/{})".format(pindex, ptotal))

            loader.config[".gitlabemu-parallel-index"] = pindex
            loader.config[".gitlabemu-parallel-total"] = ptotal

        fix_ownership = has_docker()
        if options.no_docker:
            loader.config["hide_docker"] = True
            fix_ownership = False

        docker_job = loader.get_docker_image(jobname)
        if docker_job:
            gwt = git_worktree(rootdir)
            if gwt:
                print(f"f{rootdir} is a git worktree, adding {gwt} as a docker volume.")
                # add the real git repo as a docker volume
                volumes = get_user_config_value(cfg, "docker", name="volumes", default=[])
                volumes.append(f"{gwt}:{gwt}:ro")
                override_user_config_value("docker", "volumes", volumes)
        else:
            fix_ownership = False

        apply_user_config(loader, cfg, is_docker=docker_job)

        if not is_linux():
            fix_ownership = False

        for item in options.revars:
            patt = re.compile(item)
            for name in os.environ:
                if patt.search(name):
                    loader.config["variables"][name] = os.environ.get(name)

        for item in options.var:
            var = item.split("=", 1)
            if len(var) == 2:
                name, value = var[0], var[1]
            else:
                name = var[0]
                value = os.environ.get(name, None)

            if value is not None:
                loader.config["variables"][name] = value

        if options.download and not options.FROM:
            die("--download requires --from PIPELINE")

        if options.FROM:
            server, extra = options.FROM.split("/", 1)
            project_path, pipeline_id = extra.rsplit("/", 1)
            gitlab = gitlab_api(cfg, server, secure=not options.insecure)
            # get project
            project = gitlab.projects.get(project_path)
            # get pipeline
            pipeline = project.pipelines.get(int(pipeline_id))
            pipeline_jobs = pipeline.jobs.list(all=True)

            if options.download:
                download_from_jobs = [jobname]
            else:
                jobobj = configloader.load_job(loader.config, jobname)
                download_from_jobs = jobobj.dependencies

            # download what we need
            upsteam_jobs: List[ProjectPipelineJob] = [x for x in pipeline_jobs if x.name in download_from_jobs]
            for upstream in upsteam_jobs:
                print(f"Fetching {upstream.name} artifacts from {options.FROM}..")
                artifact_url = f"{gitlab.api_url}/projects/{project.id}/jobs/{upstream.id}/artifacts"

                # stream it into zipfile
                resp = gitlab.session.get(artifact_url, headers={"PRIVATE-TOKEN": gitlab.private_token}, stream=True)
                resp.raise_for_status()
                seekable = stream_response.ResponseStream(resp.iter_content(4096))
                with zipfile.ZipFile(seekable) as zf:
                    for item in zf.infolist():
                        print(f"Saving {item.filename} ..")
                        zf.extract(item)
            if options.download:
                sys.exit(0)

        if options.enter_shell:
            if options.FULL:
                print("-i is not compatible with --full", file=sys.stderr)
                sys.exit(1)
        loader.config["enter_shell"] = options.enter_shell
        loader.config["before_script_enter_shell"] = options.before_script_enter_shell
        loader.config["shell_is_user"] = options.shell_is_user

        if options.before_script_enter_shell and is_windows():
            print("--before-script is not yet supported on windows", file=sys.stderr)
            sys.exit(1)

        if options.error_shell:
            loader.config["error_shell"] = [options.error_shell]
        try:
            executed_jobs = set()
            execute_job(loader.config, jobname, seen=executed_jobs, recurse=options.FULL)
        finally:
            if has_docker() and fix_ownership:
                if is_linux() or is_apple():
                    if os.getuid() > 0:
                        print("Fixing up local file ownerships..")
                        restore_path_ownership(os.getcwd())
                        print("finished")
        print("Build complete!")
