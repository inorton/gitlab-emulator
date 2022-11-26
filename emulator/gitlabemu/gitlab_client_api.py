import contextlib
import os
import random
import re
import shutil
import subprocess
import time
import zipfile
import requests
import tempfile
import certifi
import multiprocessing
from functools import lru_cache
from threading import RLock
from typing import Optional, Set, Tuple, Iterable, List, Any, Dict
from urllib.parse import urlparse
from gitlab import Gitlab, GitlabGetError
from gitlab.v4.objects import Project
from urllib3.exceptions import InsecureRequestWarning

from .helpers import die, note, get_git_remote_urls, is_linux
from .userconfig import get_user_config_context
from .userconfigdata import GitlabServer

GITLAB_SERVER_ENV = "GLE_GITLAB_SERVER"
GITLAB_PROJECT_ENV = "GLE_GITLAB_PROJECT"
SYSTEM_CA_CERTS = "/etc/ssl/certs/ca-certificates.crt"


class GitlabIdent:
    def __init__(self, server=None, project=None, pipeline=None, gitref=None, secure=True):
        self.server: Optional[str] = server
        self.project: Optional[str] = project
        self.pipeline: Optional[int] = pipeline
        self.gitref: Optional[str] = gitref
        self.secure: Optional[bool] = secure

    def __str__(self):
        ret = ""
        attribs = []
        if self.server:
            attribs.append(f"server={self.server}")
        if self.project:
            attribs.append(f"project={self.project}")
        if self.gitref:
            attribs.append(f"git_ref={self.gitref}")
        elif self.pipeline:
            attribs.append(f"id={self.pipeline}")

        return f"Pipeline {', '.join(attribs)}"


class TaskError(Exception):
    def __init__(self, task, inner):
        self.task = task
        self.inner = inner


class PipelineError(Exception):
    def __init__(self, pipeline: str):
        super(PipelineError, self).__init__()
        self.pipeline = pipeline


class PipelineInvalid(PipelineError):
    def __init__(self, pipeline: str):
        super(PipelineInvalid, self).__init__(pipeline)

    def __str__(self):
        return f"'{self.pipeline}' is not a valid pipeline specification"


class PipelineNotFound(PipelineError):
    def __init__(self, pipeline):
        super(PipelineNotFound, self).__init__(pipeline)

    def __str__(self):
        return f"Cannot find pipeline '{self.pipeline}'"


def gitlab_api(alias: str, secure=True) -> Gitlab:
    """Create a Gitlab API client"""
    ctx = get_user_config_context()
    server = None
    token = None
    for item in ctx.gitlab.servers:
        if item.name == alias:
            server = item.server
            token = item.token
            break

        parsed = urlparse(item.server)
        if parsed.hostname == alias:
            server = item.server
            token = item.token
            break

    if not server:
        note(f"using {alias} as server hostname")
        server = alias
        if "://" not in server:
            server = f"https://{server}"

    environment_token = os.getenv("GITLAB_PRIVATE_TOKEN", None)
    if environment_token:
        token = environment_token
        note("Using GITLAB_PRIVATE_TOKEN for authentication")

    if not token:
        die(f"Could not find a configured token for {alias} or GITLAB_PRIVATE_TOKEN not set")

    client = Gitlab(url=server, private_token=token, ssl_verify=secure)
    if secure:
        gitlab_session_head(client.session, server)
    return client


def parse_gitlab_from_arg(arg: str, prefer_gitref: Optional[bool] = False) -> GitlabIdent:
    """Decode an identifier into a project and optionally pipeline ID or git reference"""
    # server/group/project/1234    = pipeline 1234 from server/group/project
    # 1234                         = pipeline 1234 from current project
    # server/group/project=gitref  = last successful pipeline for group/project at gitref commit/tag/branch
    # =gitref                      = last successful pipeline at the gitref of the current project
    gitref = None
    project = None
    server = None
    pipeline = None
    if arg.isnumeric():
        pipeline = int(arg)
    elif prefer_gitref:
        gitref = arg
        arg = ""
    elif "=" in arg:
        arg, gitref = arg.rsplit("=", 1)

    if "/" in arg:
        parts = arg.split("/")
        if len(parts) > 2:
            server = parts[0]
            if parts[-1].isnumeric():
                pipeline = int(parts[-1])
                project = "/".join(parts[1:-1])
            else:
                project = "/".join(parts[1:])

    return GitlabIdent(project=project,
                       server=server,
                       pipeline=pipeline,
                       gitref=gitref)


def find_project_pipeline(project,
                          pipeline: Optional[int] = 0,
                          ref: Optional[str] = None):
    """Get a pipeline from the current project"""
    try:
        if pipeline:
            return project.pipelines.get(pipeline)
        match = {}
        if ref:
            match["ref"] = ref

        found = project.pipelines.list(sort="desc", order_by="updated_at", page=1, pagesize=1, **match)
        if not found:
            raise PipelineNotFound(str(match))
        return found[0]

    except GitlabGetError as err:
        if err.response_code == 404:
            raise PipelineNotFound(str(pipeline))


def get_pipeline(fromline, secure: Optional[bool] = True):
    """Get a pipeline"""
    pipeline = None
    ident = parse_gitlab_from_arg(fromline)
    if not secure:
        note("TLS server validation disabled by --insecure")
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    if not ident.pipeline:
        if not ident.gitref:
            raise PipelineInvalid(fromline)

    if not ident.server:
        cwd = os.getcwd()
        gitlab, project, remotename = get_gitlab_project_client(cwd, secure)
    else:
        gitlab = gitlab_api(ident.server, secure=secure)
        # get project
        project = gitlab.projects.get(ident.project)

    if not project:
        raise PipelineInvalid(fromline)

    # get pipeline
    if ident.pipeline:
        try:
            pipeline = find_project_pipeline(project, pipeline=ident.pipeline)
        except GitlabGetError as err:
            if err.response_code == 404:
                raise PipelineNotFound(fromline)

    return gitlab, project, pipeline

_CA_FIXUP_LOCK = RLock()


@lru_cache(1)
def get_ca_bundle() -> str:
    bundles = []
    for env in ["REQUESTS_CA_BUNDLE", "CI_SERVER_TLS_CA_FILE"]:
        bundle = os.getenv(env, None)
        if bundle and os.path.isfile(bundle):
            note(f"Using extra CAs from {env} in {bundle}")
            bundles.append(bundle)
    certs = certifi.contents()
    if os.path.exists(SYSTEM_CA_CERTS) and not os.path.samefile(SYSTEM_CA_CERTS, certifi.where()):
        with open(SYSTEM_CA_CERTS, "r") as etc_certs:
            certs += etc_certs.read()
    for bundle in bundles:
        with open(bundle, "r") as data:
            certs += data.read()
    return certs


@contextlib.contextmanager
def posix_cert_fixup():
    with _CA_FIXUP_LOCK:
        if "GLE_CA_BUNDLE" not in os.environ:
            with tempfile.TemporaryDirectory() as tempdir:
                os.environ["GLE_CA_BUNDLE"] = "1"
                certs = get_ca_bundle()
                new_bundle = os.path.join(tempdir, "ca-certs.pem")
                with open(new_bundle, "w") as data:
                    data.write(certs)
                os.environ["REQUESTS_CA_BUNDLE"] = new_bundle
                try:
                    yield
                finally:
                    del os.environ["GLE_CA_BUNDLE"]
                    del os.environ["REQUESTS_CA_BUNDLE"]
        else:
            yield


def gitlab_session_head(session, geturl, **kwargs):
    """HEAD using requests to try different CA options"""
    with posix_cert_fixup():
        return session.head(geturl, **kwargs)


def get_one_file(session: requests.Session,
                 url: str,
                 outfile: str,
                 headers: Optional[dict] = None) -> str:
    """Download one file from a gitlab url and save it"""
    outdir = os.path.dirname(outfile)
    partfile = outfile + ".part"
    if os.path.exists(outfile):
        os.unlink(outfile)
    os.makedirs(outdir, exist_ok=True)
    with posix_cert_fixup():
        resp = session.get(url, headers=headers, stream=True)
        resp.raise_for_status()
        with open(partfile, "wb") as data:
            shutil.copyfileobj(resp.raw, data, length=2 * 1024 * 1024)
        shutil.move(partfile, outfile)
    return outfile


def unpack_one_artifact(temp_zip_file: str, outdir: str, name: str,
                        progress: Optional[bool] = True):
    """Extract a downloaded artifact zip"""
    if progress:
        note(f" Extracting artifacts from job '{name}' ..")
    with open(temp_zip_file, "rb") as compressed:
        with zipfile.ZipFile(compressed) as zf:
            for item in zf.infolist():
                savefile = os.path.join(outdir, item.filename)
                if os.path.exists(savefile):
                    note(f"  Warning: File {savefile} already exists, overwriting..")
                if progress:
                    note(f"  Saving {savefile} ..")
                zf.extract(item, path=outdir)


def multi_download_unpack_jobs(gitlab: Gitlab,
                               project,
                               outdir: str,
                               jobs,
                               callback: Optional[List[str]] = None,
                               headers: Optional[dict] = None,
                               export_mode: Optional[bool] = False,
                               workers: Optional[int] = None):
    """Download and unpack multiple jobs, use parallelization if in export mode"""
    if workers is None:
        workers = (multiprocessing.cpu_count() - 1)
        if workers < 1:
            workers = 1
        if workers > 4:
            workers = 4
    if not export_mode:
        workers = 1
    downloads = []

    for fetch_job in jobs:
        artifact_url = None
        if [x for x in fetch_job.artifacts if x["file_type"] == "archive"]:
            artifact_url = f"{gitlab.api_url}/projects/{project.id}/jobs/{fetch_job.id}/artifacts"
        jobdir = outdir
        trace_url = None

        if export_mode:
            jobdir = os.path.join(outdir, sanitize_pathname(fetch_job.name))
            trace_url = f"{gitlab.api_url}/projects/{project.id}/jobs/{fetch_job.id}/trace"

        downloads.append([fetch_job.name,
                          gitlab.session.auth,
                          callback,
                          jobdir,
                          artifact_url,
                          trace_url,
                          headers])
    if export_mode:
        random.shuffle(downloads)
    progress = 0
    sizes = []
    times = []
    started = time.monotonic()
    with multiprocessing.Pool(processes=workers) as pool:
        manager = multiprocessing.Manager()
        printmutex = manager.Lock()
        execmutex = manager.Lock()
        tasks = []
        for args in downloads:
            args.append(printmutex)
            args.append(execmutex)
            task = pool.apply_async(downloader, args)
            tasks.append(task)

        for task in tasks:
            try:
                size, download_time = task.get()
            except TaskError as err:
                note(f"error! failed downloading {err.task}!")
                raise err.inner
            sizes.append(size)
            times.append(download_time)
            progress += 1
            sofar = time.monotonic() - started
            note(f"{int(sofar):-4}s {progress:-3}/{len(downloads):-3} completed.")
    finished = time.monotonic()
    duration = finished - started
    total_downloaded = sum(sizes)
    total_times = sum(times)
    combined_rate = total_downloaded / total_times
    note(f"All downloads complete: {int(total_downloaded/1024/1024)} mb.")
    note(f"Combined transfer rate: {int(combined_rate/1024/1024)} mb/s.")
    note(f"Total time {int(duration)} sec.")


def sanitize_pathname(path: str) -> str:
    path = path.lower()
    path = re.sub(r"[^a-z\d\-.]", "_", path)
    return path


def downloader(jobname: str,
               auth: Optional[Any],
               cbscript: Optional[List[str]],
               outdir: str,
               archive_url: Optional[str],
               trace_url: Optional[str],
               hdrs: Optional[dict],
               printlock: multiprocessing.Lock,
               execlock: multiprocessing.Lock):
    try:
        session = requests.Session()
        session.auth = auth
        started = time.monotonic()
        size = 0
        archive_file = None
        if archive_url:
            archive_file = os.path.join(outdir, "archive.zip")
            get_one_file(session, archive_url, archive_file, hdrs)
            size += os.path.getsize(archive_file)
        if trace_url:
            trace_file = os.path.join(outdir, "trace.log")
            get_one_file(session, trace_url, trace_file, hdrs)
            size += os.path.getsize(trace_file)
        ended = time.monotonic()
        duration = ended - started
        rate = size / duration

        with printlock:
            note(f"Fetching job {jobname} .. done {int(size / 1024)} kb, {int(rate / 1024)} kb/s")
        if archive_file:
            with printlock:
                note(f"Unpack job {jobname} archive into {outdir} ..")
            unpack_one_artifact(archive_file, outdir, jobname, progress=False)
            os.unlink(archive_file)
            with printlock:
                note(f"Unpack job {jobname} archive into {outdir} .. done")
        if cbscript:
            args = []
            for x in cbscript:
                args.append(x.replace("%p", outdir))
            with execlock:
                with printlock:
                    note(f"Executing '{' '.join(args)}'..")
                subprocess.check_call(args, shell=False)
        return size, duration
    except Exception as err:
        raise TaskError(jobname, err)


def do_gitlab_fetch(from_pipeline: str,
                    get_jobs: Iterable[str],
                    download_to: Optional[str] = None,
                    export_to: Optional[str] = False,
                    callback: Optional[List[str]] = None,
                    tls_verify: Optional[bool] = True):
    """Fetch builds and logs from gitlab"""
    gitlab, project, pipeline = get_pipeline(from_pipeline, secure=tls_verify)
    gitlab.session.verify = tls_verify  # hmm ?
    pipeline_jobs = pipeline.jobs.list(all=True)
    known_jobs = [x.name for x in pipeline_jobs]
    want_jobs = []
    if get_jobs:
        want_jobs = list(get_jobs)
        for item in list(want_jobs):
            if item not in known_jobs:

                errmsg = f"Pipeline {pipeline.id} does not contain a job named '{item}'"
                similar = [name for name in known_jobs if "/" in name and name.startswith(item)]
                if not similar:
                    die(errmsg)
                want_jobs.extend(similar)
            else:
                want_jobs.append(item)

    fetch_jobs = [x for x in pipeline_jobs if not want_jobs or x.name in want_jobs]

    assert export_to or download_to
    outdir = download_to
    if export_to:
        mode = "Exporting"
        outdir = export_to
    else:
        mode = "Fetching"
    note(f"{mode} {len(fetch_jobs)} jobs from {pipeline.web_url}..")
    headers = {}
    if gitlab.private_token:
        headers = {"PRIVATE-TOKEN": gitlab.private_token}
    multi_download_unpack_jobs(gitlab, project, outdir, fetch_jobs,
                               callback=callback,
                               headers=headers,
                               export_mode=export_to)


def remote_servers(remotes: Dict[str, str]) -> Dict[str, str]:
    """From a map of git remotes, Get a map of git remotes to server addresses"""
    servers: Dict[str, str] = {}
    for remote_name in remotes:
        remote_url = remotes[remote_name]
        if remote_url.startswith("git@") and remote_url.endswith(".git"):
            if ":" in remote_url:
                lhs, rhs = remote_url.split(":", 1)
                host = lhs.split("@", 1)[1]
                project_path = rhs.rsplit(".", 1)[0].lstrip("/")
                servers[remote_name] = f"{host}/{project_path}"
        elif "://" in remote_url and remote_url.startswith("http"):
            parsed = urlparse(remote_url)
            host = parsed.hostname
            project_path = parsed.path.rsplit(".", 1)[0].lstrip("/")
            servers[remote_name] = f"{host}/{project_path}"
    return servers


def find_gitlab_project_config(servers: Dict[str, str]) -> Optional[GitlabIdent]:
    """From a list of git remotes and project servers addresses find the named gitlab config entry if any"""
    ctx = get_user_config_context()
    ident: Optional[GitlabIdent] = None
    for remote in servers:
        remote_host, remote_path = servers[remote].split("/", 1)
        https_remote = f"https://{remote_host}"
        for cfg in ctx.gitlab.servers:
            if cfg.server == https_remote:
                ident = GitlabIdent(server=remote_host, project=remote_path, secure=cfg.tls_verify)
                break
    return ident


def get_gitlab_project_client(repo: str, secure=True) -> Tuple[Optional[Gitlab], Optional[Project], Optional[str]]:
    """Get the gitlab client, project and git remote name for the given git repo"""
    override_server = os.getenv(GITLAB_SERVER_ENV)
    override_project = os.getenv(GITLAB_PROJECT_ENV)
    client = None
    project = None
    git_remote = None

    if override_server and override_project:
        ident = GitlabIdent(server=override_server, project=override_project)
        remotes = []
    else:
        # in here, we need to figure out the gitlab server by looking
        # at the available git remotes
        remotes = get_git_remote_urls(repo)
        if not remotes:
            die(f"Folder {repo} has no remotes, is it a git repo?")

        possible_servers = remote_servers(remotes)
        ident = find_gitlab_project_config(possible_servers)
        if ident and ident.secure:
            secure = ident.secure

        if not ident:
            note(f"Could not find a gitlab config for {repo}")
            if len(possible_servers) == 1:
                gitlab_host, gitlab_path = list(possible_servers.values())[0].split("/", 1)
                git_remote = list(possible_servers.keys())[0]
                ident = GitlabIdent(server=gitlab_host, project=gitlab_path)

    if ident:
        # we have an ident, try to find the gitlab config
        api = gitlab_api(ident.server, secure=secure)
        api.auth()
        for proj in api.projects.list(membership=True, all=True):
            if ident.project:
                if proj.path_with_namespace == ident.project:
                    project = proj
                    client = api
                    break

        if remotes and project:
            project_remotes = [project.ssh_url_to_repo, project.http_url_to_repo]
            for remote in remotes:
                if remotes[remote] in project_remotes:
                    git_remote = remote
                    break

    return client, project, git_remote


def get_current_project_client(tls_verify: Optional[bool] = True,
                               need_remote: Optional[bool] = True) -> Tuple[Gitlab, Project, str]:
    """Get the requested/current gitlab client, gitlab project and optional git remote"""
    cwd = os.getcwd()
    client, project, remotename = get_gitlab_project_client(cwd, tls_verify)

    if not (client and project):
        die("Could not find a gitlab server configuration, please add one with 'gle-config gitlab'")

    if need_remote:
        if not remotename:  # pragma: no-cover
            die("Could not find a gitlab configuration that matches any of our git remotes")
    return client, project, remotename
