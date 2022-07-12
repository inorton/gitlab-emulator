import contextlib
import os
import shutil
import time
import zipfile
import requests
import tempfile
from typing import Optional, List, Set, Tuple
from urllib.parse import urlparse
from gitlab import Gitlab, GitlabGetError
from gitlab.v4.objects import ProjectPipelineJob, Project
from urllib3.exceptions import InsecureRequestWarning

from .helpers import die, note, make_path_slug, get_git_remote_urls
from .userconfig import get_user_config_context


class GitlabIdent:
    def __init__(self, server=None, project=None, pipeline=None, gitref=None):
        self.server: Optional[str] = server
        self.project: Optional[str] = project
        self.pipeline: Optional[int] = pipeline
        self.gitref: Optional[str] = gitref

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


def get_pipeline(fromline, secure: Optional[bool] = True):
    """Get a pipeline"""
    pipeline = None
    ident = parse_gitlab_from_arg(fromline)
    if not secure:
        note("TLS server validation disabled by --insecure")
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

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
            pipeline = project.pipelines.get(ident.pipeline)
        except GitlabGetError as err:
            if err.response_code == 404:
                raise PipelineNotFound(fromline)

    return gitlab, project, pipeline


@contextlib.contextmanager
def ca_bundle_error(func: callable):
    try:
        yield func()
    except requests.exceptions.SSLError:  # pragma: no cover
        # validation was requested but cert was invalid,
        # tty again without the gitlab-supplied CA cert and try the system ca certs
        if "REQUESTS_CA_BUNDLE" not in os.environ:
            raise
        note(f"warning: Encountered TLS/SSL error, retrying with only system ca certs")
        del os.environ["REQUESTS_CA_BUNDLE"]
        yield func()


def gitlab_session_head(session, geturl, **kwargs):
    """HEAD using requests to try different CA options"""
    with ca_bundle_error(lambda: session.head(geturl, **kwargs)) as resp:
        return resp


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
        reldir = os.path.relpath(outdir, os.getcwd())

        headers = {}
        if gitlab.private_token:
            headers = {"PRIVATE-TOKEN": gitlab.private_token}

        note(f"{mode} {fetch_job.name} artifacts from {from_pipeline}..")
        archive_artifact = [x for x in fetch_job.artifacts if x["file_type"] == "archive"]
        if archive_artifact:
            artifact_compressed_size = archive_artifact[0]["size"]
            artifact_url = f"{gitlab.api_url}/projects/{project.id}/jobs/{fetch_job.id}/artifacts"
            note(f"Get {artifact_url} ({int(artifact_compressed_size/1024)} kb) ..")
            temp_zip_dir = tempfile.mkdtemp(dir=os.getcwd(), prefix=".temp-gle-download")
            try:
                started_fetch = time.time()
                with ca_bundle_error(
                        lambda: gitlab.session.get(artifact_url, headers=headers, stream=True)) as resp:
                    resp.raise_for_status()
                temp_zip_file = os.path.join(temp_zip_dir, "artifacts.zip")
                with open(temp_zip_file, "wb") as zf:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            zf.write(chunk)
                with open(temp_zip_file, "rb") as compressed:
                    with zipfile.ZipFile(compressed) as zf:
                        for item in zf.infolist():
                            note(f"Saving {reldir}/{item.filename} ..")
                            zf.extract(item, path=outdir)
                completed_fetch = time.time()
                duration = completed_fetch - started_fetch
                fetch_unpack_rate = artifact_compressed_size / duration
                note("Fetched/Unpacked at {} kb/s ({} kb)".format(
                    int(fetch_unpack_rate / 1024.0),
                    int(artifact_compressed_size / 1024.0)
                ))
            finally:
                shutil.rmtree(temp_zip_dir)
        else:
            note(f"Job {fetch_job.name} has no artifacts")

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
