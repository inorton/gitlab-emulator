import os
import shutil
import zipfile
import requests
from typing import Optional, List, cast, Set, Tuple
from typing.io import IO
from urllib.parse import urlparse
from gitlab import Gitlab, GitlabGetError
from gitlab.v4.objects import ProjectPipelineJob, Project
from urllib3.exceptions import InsecureRequestWarning

from . import stream_response
from .helpers import die, note, make_path_slug, get_git_remote_urls
from .userconfig import get_user_config_context


class GitlabIdent:
    def __init__(self, server=None, project=None, pipeline=None, gitref=None):
        self.server: Optional[str] = server
        self.project: Optional[str] = project
        self.pipeline: Optional[int] = pipeline
        self.gitref: Optional[str] = gitref


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

    client = Gitlab(url=server, private_token=token, ssl_verify=secure)
    return client


def parse_gitlab_from_arg(arg: str) -> GitlabIdent:
    """Decode an identifier into a project and optionally pipeline ID or git reference"""
    # server/group/project/1234    = pipeline 1234 from server/group/project
    # 1234                         = pipeline 1234 from current project
    # server/group/project=gitref  = last successful pipeline for group/project at gitref commit/tag/branch
    # =gitref                      = last successful pipeline at the gitref of the current project
    gitref = None
    project = None
    server = None
    pipeline = None
    if "=" in arg:
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
    elif arg.isnumeric():
        pipeline = int(arg)

    return GitlabIdent(project=project,
                       server=server,
                       pipeline=pipeline,
                       gitref=gitref)


def get_pipeline(fromline, secure: Optional[bool] = True):
    """Get a pipeline"""
    pipeline = None
    ident = parse_gitlab_from_arg(fromline)
    if not ident.server:
        raise PipelineInvalid(fromline)
    if not secure:
        note("TLS server validation disabled by --insecure")
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    gitlab = gitlab_api(ident.server, secure=secure)
    # get project
    project = gitlab.projects.get(ident.project)
    # get pipeline
    if ident.pipeline:
        try:
            pipeline = project.pipelines.get(ident.pipeline)
        except GitlabGetError as err:
            if err.response_code == 404:
                raise PipelineNotFound(fromline)

    return gitlab, project, pipeline


def gitlab_session_get(gitlab, geturl, **kwargs):
    """Get using requests and retry TLS errors"""
    try:
        return gitlab.session.get(geturl, **kwargs)
    except requests.exceptions.SSLError:  # pragma: no cover
        # validation was requested but cert was invalid,
        # tty again without the gitlab-supplied CA cert and try the system ca certs
        if "REQUESTS_CA_BUNDLE" in os.environ:
            note(f"warning: Encountered TLS/SSL error getting {geturl}), retrying with system ca certs")
            del os.environ["REQUESTS_CA_BUNDLE"]
            return gitlab.session.get(geturl, **kwargs)
        raise


def do_gitlab_fetch(from_pipeline: str,
                    get_jobs: List[str],
                    download_to: Optional[str] = None,
                    export_to: Optional[str] = False,
                    tls_verify: Optional[bool] = True):
    """Fetch builds and logs from gitlab"""
    gitlab, project, pipeline = get_pipeline(from_pipeline, secure=tls_verify)
    gitlab.session.verify = tls_verify  # hmm ?
    pipeline_jobs = pipeline.jobs.list(all=True)
    fetch_jobs = pipeline_jobs
    assert export_to or download_to
    outdir = download_to
    if export_to:
        mode = "Exporting"
    else:
        mode = "Fetching"
        fetch_jobs: List[ProjectPipelineJob] = [x for x in pipeline_jobs if x.name in get_jobs]

    for fetch_job in fetch_jobs:
        if export_to:
            slug = make_path_slug(fetch_job.name)
            outdir = os.path.join(export_to, slug)
            os.makedirs(outdir, exist_ok=True)

        note(f"{mode} {fetch_job.name} artifacts from {from_pipeline}..")
        artifact_url = f"{gitlab.api_url}/projects/{project.id}/jobs/{fetch_job.id}/artifacts"
        reldir = os.path.relpath(outdir, os.getcwd())
        # stream it into zipfile
        headers = {}
        if gitlab.private_token:
            headers = {"PRIVATE-TOKEN": gitlab.private_token}
        resp = gitlab_session_get(gitlab, artifact_url, headers=headers, stream=True)
        if resp.status_code == 404:
            note(f"Job {fetch_job.name} has no artifacts")
        else:
            resp.raise_for_status()
            seekable = cast(IO, stream_response.ResponseStream(resp.iter_content(4096)))
            with zipfile.ZipFile(seekable) as zf:
                for item in zf.infolist():
                    note(f"Saving {reldir}/{item.filename} ..")
                    zf.extract(item, path=outdir)

        if export_to:
            # also get the trace and junit reports
            logfile = os.path.join(outdir, "trace.log")
            note(f"Saving log to {reldir}/trace.log")
            trace_url = f"{gitlab.api_url}/projects/{project.id}/jobs/{fetch_job.id}/trace"
            with open(logfile, "wb") as logdata:
                resp = gitlab.session.get(trace_url, headers=headers, stream=True)
                resp.raise_for_status()
                shutil.copyfileobj(resp.raw, logdata)


def get_gitlab_project_client(repo: str, secure=True) -> Tuple[Optional[Gitlab], Optional[Project], Optional[str]]:
    """Get the gitlab client, project and git remote name for the given git repo"""
    remotes = get_git_remote_urls(repo)
    ident: Optional[GitlabIdent] = None
    ssh_remotes: Set[str] = set()
    http_remotes: Set[str] = set()

    for remote_name in remotes:
        host = None
        project = None
        remote_url = remotes[remote_name]
        if remote_url.startswith("git@") and remote_url.endswith(".git"):
            ssh_remotes.add(remote_name)
            if ":" in remote_url:
                lhs, rhs = remote_url.split(":", 1)
                host = lhs.split("@", 1)[1]
                project = rhs.rsplit(".", 1)[0]
        elif "://" in remote_url and remote_url.startswith("http"):
            http_remotes.add(remote_url)
            parsed = urlparse(remote_url)
            host = parsed.hostname
            project = parsed.path.rsplit(".", 1)[0]

        if host and project:
            ident = GitlabIdent(server=host, project=project)
            break

    client = None
    project = None
    git_remote = None

    if ident:
        api = gitlab_api(ident.server, secure=secure)
        api.auth()
        for proj in api.projects.list(membership=True, all=True):
            project_remotes = [proj.ssh_url_to_repo, proj.http_url_to_repo]
            for remote in remotes:
                if remotes[remote] in project_remotes:
                    git_remote = remote
                    client = api
                    project = proj
                    break

    return client, project, git_remote
