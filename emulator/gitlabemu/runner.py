import re
import shutil
import subprocess
import sys
import os
import argparse
import zipfile
from typing import Optional, List
from gitlab.v4.objects import ProjectPipelineJob
from urllib3.exceptions import InsecureRequestWarning

from . import configloader
from . import stream_response
from .docker import has_docker
from .localfiles import restore_path_ownership
from .helpers import is_apple, is_linux, is_windows, git_worktree, make_path_slug
from .userconfig import load_user_config, get_user_config_value, override_user_config_value, USER_CFG_ENV
import requests
from gitlab import Gitlab

CONFIG_DEFAULT = ".gitlab-ci.yml"

parser = argparse.ArgumentParser(prog="{} -m gitlabemu".format(os.path.basename(sys.executable)))
parser.add_argument("--list", "-l", dest="LIST", default=False,
                    action="store_true",
                    help="List runnable jobs")
parser.add_argument("--version", default=False, action="store_true")
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

parser.add_argument("--export", type=str, dest="export", metavar="EXPORT",
                    help="Download JOB logs and artifacts to EXPORT/JOBNAME (requires --from)")

parser.add_argument("--completed", default=False, action="store_true",
                    help="List (implies --list) all currently completed jobs in the --from pipeline")

parser.add_argument("--insecure", "-k", dest="insecure", default=False, action="store_true",
                    help="Ignore TLS certificate errors when fetching from remote servers")

if is_windows():
    shellgrp = parser.add_mutually_exclusive_group()
    shellgrp.add_argument("--powershell", default=False, action="store_true",
                          help="Force use of powershell for windows jobs")
    shellgrp.add_argument("--cmd", default=False, action="store_true", dest="cmd_shell",
                          help="Force use of cmd for windows jobs")

parser.add_argument("JOB", type=str, default=None,
                    nargs="?",
                    help="Run this named job")


def die(msg):
    """print an error and exit"""
    print("error: " + str(msg), file=sys.stderr)
    sys.exit(1)


def note(msg):
    """Print to stderr"""
    print(msg, file=sys.stderr)


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
    server = None
    token = None
    for item in servers:
        if item.get("name") == alias:
            server = item.get("server")
            token = item.get("token")
            if not server:
                die(f"no server address for alias {alias}")
            if not token:
                die(f"no api-token for alias {alias} ({server})")
            break

    if not server:
        note(f"using {alias} as server hostname")
        server = alias
        if "://" not in server:
            server = f"https://{server}"

    ca_cert = os.getenv("CI_SERVER_TLS_CA_FILE", None)
    if ca_cert is not None:
        note("Using CI_SERVER_TLS_CA_FILE CA cert")
        os.environ["REQUESTS_CA_BUNDLE"] = ca_cert
        secure = True

    if not token:
        token = os.getenv("GITLAB_PRIVATE_TOKEN", None)
        if token:
            note("Using GITLAB_PRIVATE_TOKEN for authentication")

    if not token:
        die(f"Could not find a configured token for {alias} or GITLAB_PRIVATE_TOKEN not set")

    if server and token:
        client = Gitlab(url=server, private_token=token, ssl_verify=secure)
        return client

    die(f"Cannot find local configuration for server {alias}")


def get_pipeline(cfg, fromline, secure: Optional[bool] = True):
    """Get a pipeline"""
    server, extra = fromline.split("/", 1)
    project_path, pipeline_id = extra.rsplit("/", 1)
    if not secure:
        note("TLS server validation disabled by --insecure")
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    gitlab = gitlab_api(cfg, server, secure=secure)
    # get project
    project = gitlab.projects.get(project_path)
    # get pipeline
    pipeline = project.pipelines.get(int(pipeline_id))
    return gitlab, project, pipeline


def do_gitlab_from(options: argparse.Namespace, cfg, loader):
    """Perform actions using a gitlab server"""
    if options.download and not options.FROM:
        die("--download requires --from PIPELINE")
    if options.FROM:
        gitlab, project, pipeline = get_pipeline(cfg, options.FROM, secure=not options.insecure)
        if options.insecure:
            gitlab.session.verify = False
        pipeline_jobs = pipeline.jobs.list(all=True)

        if options.export:
            options.download = True

        if options.LIST:
            # print the jobs in the pipeline

            jobs = list(pipeline_jobs)
            if options.completed:
                jobs = [x for x in jobs if x.status == "success"]
                note(f"Listing completed jobs in {options.FROM}")
            else:
                note(f"Listing jobs in {options.FROM}")
            names = sorted([x.name for x in jobs])
            for name in names:
                print(name)
            return

        outdir = os.getcwd()
        if options.download:
            # download a job
            download_from_jobs = [options.JOB]
            if options.export:
                # export the job
                note(f"Export '{options.JOB}'")
                slug = make_path_slug(options.JOB)
                outdir = os.path.join(options.export, slug)
                os.makedirs(outdir, exist_ok=True)
            else:
                note(f"Download '{options.JOB}' artifacts")
        else:
            note(f"Download artifacts required by '{options.JOB}'")
            # download jobs needed by a job
            jobobj = configloader.load_job(loader.config, options.JOB)
            download_from_jobs = jobobj.dependencies

        def gitlab_session_get(geturl, **kwargs):
            """Get using requests and retry TLS errors"""
            try:
                return gitlab.session.get(geturl, **kwargs)
            except requests.exceptions.SSLError:
                # validation was requested but cert was invalid,
                # tty again without the gitlab-supplied CA cert and try the system ca certs
                if "REQUESTS_CA_BUNDLE" in os.environ:
                    note(f"warning: Encountered TLS/SSL error getting {geturl}), retrying with system ca certs")
                    del os.environ["REQUESTS_CA_BUNDLE"]
                    return gitlab.session.get(geturl, **kwargs)
                raise

        # download what we need
        mode = "Fetching"
        if options.export:
            mode = "Exporting"
        upsteam_jobs: List[ProjectPipelineJob] = [x for x in pipeline_jobs if x.name in download_from_jobs]
        for upstream in upsteam_jobs:
            note(f"{mode} {upstream.name} artifacts from {options.FROM}..")
            artifact_url = f"{gitlab.api_url}/projects/{project.id}/jobs/{upstream.id}/artifacts"
            reldir = os.path.relpath(outdir, os.getcwd())
            # stream it into zipfile
            headers = {}
            if gitlab.private_token:
                headers = {"PRIVATE-TOKEN": gitlab.private_token}
            resp = gitlab_session_get(artifact_url, headers=headers, stream=True)
            if resp.status_code == 404:
                note(f"Job {upstream.name} has no artifacts")
            else:
                resp.raise_for_status()
                seekable = stream_response.ResponseStream(resp.iter_content(4096))
                with zipfile.ZipFile(seekable) as zf:
                    for item in zf.infolist():
                        note(f"Saving {reldir}/{item.filename} ..")
                        zf.extract(item, path=outdir)

            if options.export:
                # also get the trace and junit reports
                logfile = os.path.join(outdir, "trace.log")
                note(f"Saving log to {reldir}/trace.log")
                trace_url = f"{gitlab.api_url}/projects/{project.id}/jobs/{upstream.id}/trace"
                with open(logfile, "wb") as logdata:
                    resp = gitlab.session.get(trace_url, headers=headers, stream=True)
                    resp.raise_for_status()
                    shutil.copyfileobj(resp.raw, logdata)


def do_version():
    """Print the current package version"""
    try:
        ver = subprocess.check_output([sys.executable, "-m", "pip", "show", "gitlab-emulator"],
                                      encoding="utf-8",
                                      stderr=subprocess.STDOUT)
        for line in ver.splitlines(keepends=False):
            if "Version:" in line:
                words = line.split(":", 1)
                ver = words[1]
                break
    except subprocess.CalledProcessError:
        ver = "unknown"
    print(ver.strip())
    sys.exit(0)


def run(args=None):
    options = parser.parse_args(args)
    loader = configloader.Loader()
    yamlfile = options.CONFIG
    jobname = options.JOB

    if options.version:
        do_version()

    if options.chdir:
        if not os.path.exists(options.chdir):
            die(f"Cannot change to {options.chdir}, no such directory")
        os.chdir(options.chdir)

    if not os.path.exists(yamlfile):
        note(f"{configloader.DEFAULT_CI_FILE} not found.")
        find = configloader.find_ci_config(os.getcwd())
        if find:
            topdir = os.path.abspath(os.path.dirname(find))
            note(f"Found config: {find}")
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

    if is_windows():
        options.cmd_shell = get_user_config_value(cfg, "windows", name="cmd", default=options.cmd_shell)
        if options.cmd_shell:
            loader.config[".gitlabemu-windows-shell"] = "cmd"
        else:
            loader.config[".gitlabemu-windows-shell"] = "powershell"

    hide_dot_jobs = not options.hidden

    if options.FULL and options.parallel:
        die("--full and --parallel cannot be used together")

    if options.FROM:
        do_gitlab_from(options, cfg, loader)
        return

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
                note(f"f{rootdir} is a git worktree, adding {gwt} as a docker volume.")
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

        if options.enter_shell:
            if options.FULL:
                die("-i is not compatible with --full")
        loader.config["enter_shell"] = options.enter_shell
        loader.config["before_script_enter_shell"] = options.before_script_enter_shell
        loader.config["shell_is_user"] = options.shell_is_user

        if options.before_script_enter_shell and is_windows():
            die("--before-script is not yet supported on windows")

        if options.error_shell:
            loader.config["error_shell"] = [options.error_shell]
        try:
            executed_jobs = set()
            execute_job(loader.config, jobname, seen=executed_jobs, recurse=options.FULL)
        finally:
            if has_docker() and fix_ownership:
                if is_linux() or is_apple():
                    if os.getuid() > 0:
                        note("Fixing up local file ownerships..")
                        restore_path_ownership(os.getcwd())
                        note("finished")
        print("Build complete!")
