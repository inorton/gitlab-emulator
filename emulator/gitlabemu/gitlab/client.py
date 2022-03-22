import zipfile
from typing import List

from .. import stream_response
from ..runner import die
from ..userconfig import get_user_config_value

try:
    from gitlab import Gitlab
    from gitlab.v4.objects import ProjectPipelineJob
except ImportError:
    gitlab = None


def gitlab_api(cfg: dict, alias: str, secure=True) -> "Gitlab":
    """Create a Gitlab API client"""
    if not gitlab:
        die("Gitlab support not available on this python")
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


def gitlab_download_artifacts(cfg, pipeline_str: str, jobnames: List[str], insecure=False):
    """Download and extract the artifacts from the given jobs in a pipeline"""
    server, extra = pipeline_str
    project_path, pipeline_id = extra.rsplit("/", 1)
    gl = gitlab_api(cfg, server, secure=not insecure)
    # get project
    project = gl.projects.get(project_path)
    # get pipeline
    pipeline = project.pipelines.get(int(pipeline_id))
    pipeline_jobs = pipeline.jobs.list(all=True)
    # download what we need
    upsteam_jobs: List[ProjectPipelineJob] = [x for x in pipeline_jobs if x.name in jobnames]

    for upstream in upsteam_jobs:
        print(f"Fetching {upstream.name} artifacts from {pipeline_str}..")
        artifact_url = f"{gl.api_url}/projects/{project.id}/jobs/{upstream.id}/artifacts"

        # stream it into zipfile
        resp = gl.session.get(artifact_url, headers={"PRIVATE-TOKEN": gl.private_token}, stream=True)
        resp.raise_for_status()
        seekable = stream_response.ResponseStream(resp.iter_content(4096))
        with zipfile.ZipFile(seekable) as zf:
            for item in zf.infolist():
                print(f"Unpacking {item.filename} ..")
                zf.extract(item)
