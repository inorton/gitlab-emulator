"""Mock the GitlabAPI using requests-mock"""
import abc
import os
import random
import urllib.parse
import zipfile
from abc import ABC
from io import BytesIO
from typing import List, Optional, Union, cast
from urllib.parse import quote

from requests_mock.mocker import Mocker

MOCK_HOST = "gitlab.none"
MOCK_PROJECT_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "mocked_project")


class MockedResource(ABC):
    def __init__(self,
                 mocker: Optional[Mocker] = None
                 ):
        self._mocker: Optional[Mocker] = mocker
        self.mocks: list = []
        self.parent: Optional[Union[MockedResource, MockedIDResource, MockedIDPathResource, None]] = None

    @property
    def mocker(self) -> Mocker:
        if self.parent is not None:
            return self.parent.mocker
        return self._mocker

    @property
    @abc.abstractmethod
    def web_url(self) -> str:
        pass


class Server(MockedResource):
    def __init__(self,
                 mocker: Mocker,
                 url: str):
        super(Server, self).__init__(mocker)
        self.url = url
        self.groups: List["Group"] = []
        parsed = urllib.parse.urlparse(url)
        self.hostname = parsed.hostname
        user_url = f"{self.url}/api/v4/user"
        self.mocker.get(user_url,
                        headers={
                            "content-type": "application/json",
                        },
                        json={
                            "id": 1,
                            "username": "mock_user",
                            "name": "Mr Mock"
                        })

        self.mocks.append(
            self.mocker.get(f"{self.url}/api/v4/projects", json=self.projects_callback))
        self.mocks.append(
            self.mocker.get(f"{self.url}/api/v4/projects?membership=True", json=self.projects_callback))

    def add_group(self, grp: "Group") -> "Group":
        grp.parent = self
        self.groups.append(grp)
        grp.mocks.append(
            self.mocker.get(f"{self.url}/api/v4/projects/{grp.path}", json=grp.json_callback))
        return grp

    @property
    def projects(self) -> List["Project"]:
        found = []
        for item in self.groups:
            for project in item.projects:
                found.append(project)
        return found

    def projects_callback(self, request, context):
        context.status_code = 200
        context.headers["content-type"] = "application/json"
        resp = []
        for item in self.projects:
            resp.append(item.json())
        return resp

    @property
    def web_url(self) -> str:
        return self.url


class MockedIDResource(MockedResource, ABC):
    def __init__(self, ident: int):
        super(MockedIDResource, self).__init__()
        self.id = ident

    @property
    def server(self) -> Server:
        item = self.parent
        while item:
            if isinstance(item, Server):
                return item
            item = item.parent
        assert False, f"object {item} has no parent that is a server"


class MockedIDPathResource(MockedIDResource, ABC):
    def __init__(self, ident, path):
        super(MockedIDPathResource, self).__init__(ident)
        assert path
        self.path = path

    def __str__(self):
        return f"{self.__class__.__name__} id={self.id} {self.path}"


class Group(MockedIDPathResource):
    def __init__(self,
                 ident: int,
                 path: str,
                 name: Optional[str] = None):
        super(Group, self).__init__(ident, path)
        if not name:
            name = path.title()
        self.name = name
        self.projects: List["Project"] = []

    @property
    def web_url(self) -> str:
        return f"{self.server.url}/groups/{self.path}"

    @property
    def full_path(self) -> str:
        return self.path

    def add_project(self, prj: "Project") -> "Project":
        prj.parent = self
        self.projects.append(prj)
        mocked_url = f"{self.server.url}/api/v4/projects/{quote(prj.path_with_namespace, safe='')}"
        prj.mocks.append(self.mocker.get(mocked_url, json=prj.json_callback))
        return prj

    def json_callback(self, request, context) -> dict:
        context.status_code = 200
        context.headers["content-type"] = "application/json"
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "full_path": self.full_path,
            "web_url": self.web_url
        }


class Project(MockedIDPathResource):
    def __init__(self, ident: int, path: str):
        super(Project, self).__init__(ident, path)
        self.default_branch: Optional[str] = "main"
        self.name = self.path.title()
        self.pipelines: List["Pipeline"] = []

    def setup(self):
        list_url = f"{self.server.url}/api/v4/projects/{self.id}/pipelines"
        for url in [
            list_url,
            f"{list_url}?"
        ]:
            self.mocks.append(self.mocker.get(url, json=self.list_callback))

    @property
    def group(self) -> Group:
        return cast(Group, self.parent)

    @property
    def web_url(self) -> str:
        return f"{self.parent.web_url}/{self.path}"

    @property
    def path_with_namespace(self) -> str:
        return f"{self.parent.path}/{self.path}"

    @property
    def http_url_to_repo(self) -> str:
        return f"{self.server.url}/{self.path_with_namespace}.git"

    @property
    def ssh_url_to_repo(self) -> str:
        return f"git@{self.server.hostname}:{self.path_with_namespace}.git"

    def json_callback(self, request, context) -> dict:
        context.status_code = 200
        context.headers["content-type"] = "application/json"
        return self.json()

    def list_callback(self, request, context) -> list:
        context.status_code = 200
        context.headers["content-type"] = "application/json"
        return [x.json() for x in self.pipelines]

    def json(self):
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "path_with_namespace": self.path_with_namespace,
            "web_url": self.web_url,
            "http_url_to_repo": self.http_url_to_repo,
            "ssh_url_to_repo": self.ssh_url_to_repo,
        }

    def add_pipeline(self, pipe: "Pipeline") -> "Pipeline":
        pipe.parent = self
        self.pipelines.append(pipe)

        mocked_url = f"{self.server.url}/api/v4/projects/{pipe.project.id}/pipelines/{pipe.id}"
        pipe.mocks.append(self.mocker.get(mocked_url, json=pipe.json_callback))

        cancel_url = f"{self.server.url}/api/v4/projects/{pipe.project.id}/pipelines/{pipe.id}/cancel"
        pipe.mocks.append(self.mocker.post(cancel_url, json=pipe.json_callback))

        mocked_jobs_url = f"{mocked_url}/jobs"
        pipe.mocks.append(self.mocker.get(mocked_jobs_url, json=pipe.jobs_json_callback))
        return pipe


class Pipeline(MockedIDResource):
    def __init__(self, ident: int, iid: int):
        super(Pipeline, self).__init__(ident)
        self.iid: int = iid
        self.status: str = "success"
        self.jobs: List["Job"] = []
        self.sha = "abcd1234"
        self.ref = "main"

    @property
    def project(self) -> Project:
        return cast(Project, self.parent)

    @property
    def project_id(self) -> int:
        return self.parent.id

    @property
    def web_url(self) -> str:
        return f"{self.project.web_url}/pipelines/{self.id}"

    def json(self) -> dict:
        return {
            "id": self.id,
            "iid": self.iid,
            "project_id": self.project.id,
            "status": self.status,
            "web_url": self.web_url,
            "ref": self.ref,
            "sha": self.sha,
        }

    def json_callback(self, request, context) -> dict:
        context.status_code = 200
        context.headers["content-type"] = "application/json"
        return self.json()

    def jobs_json_callback(self, request, context) -> list:
        context.status_code = 200
        context.headers["content-type"] = "application/json"
        return [x.json() for x in self.jobs]

    def add_job(self, job: "Job") -> "Job":
        job.parent = self
        self.jobs.append(job)
        mocked_artifacts_url = f"{self.server.url}/api/v4/projects/{self.project.id}/jobs/{job.id}/artifacts"
        job.mocks.append(self.mocker.get(mocked_artifacts_url, body=job.artifacts_callback))
        mocked_trace_url = f"{self.server.url}/api/v4/projects/{self.project.id}/jobs/{job.id}/trace"
        job.mocks.append(self.mocker.get(mocked_trace_url, body=job.trace_callback))


class Artifact(MockedResource):
    def __init__(self, file_type: str, filename: str, file_format: str):
        super(Artifact, self).__init__()
        self.content = b""
        self.file_format = file_format
        self.filename = filename
        self.file_type = file_type

    @property
    def mime_type(self) -> str:
        if self.file_format == "zip":
            return "application/zip"
        elif self.file_format == "gzip":
            return "application/x-gzip"
        return "application/octet-stream"

    @property
    def size(self) -> int:
        return len(self.content)

    @property
    def web_url(self) -> str:
        return ""

    def json(self) -> dict:
        return {
            "file_format": self.file_format,
            "file_type": self.file_type,
            "size": self.size,
            "filename": self.filename,
        }


class Job(MockedIDResource):
    def __init__(self, ident: int, name: str):
        super(Job, self).__init__(ident)
        self.name: str = name
        self.ref: str = "main"
        self.status: str = "success"
        self.artifacts: List[Artifact] = []

    @property
    def pipeline(self) -> Pipeline:
        return cast(Pipeline, self.parent)

    @property
    def web_url(self) -> str:
        return f"{self.server.web_url}/-/jobs/{self.id}"

    def json(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "pipeline": self.pipeline.json(),
            "status": self.status
        }
        if self.archive_artifact:
            data["artifacts"] = [
                self.archive_artifact.json()
            ]
        return data

    @property
    def archive_artifact(self) -> Optional[Artifact]:
        for item in self.artifacts:
            if item.file_type == "archive":
                return item
        return None

    @property
    def trace_artifact(self) -> Optional[Artifact]:
        for item in self.artifacts:
            if item.file_type == "trace":
                return item
        return None

    def artifacts_callback(self, request, context) -> Optional[BytesIO]:
        return self._callback(self.archive_artifact, request, context)

    def trace_callback(self, request, context) -> Optional[BytesIO]:
        return self._callback(self.trace_artifact, request, context)

    def _callback(self, artifact, request, context) -> Optional[BytesIO]:
        if artifact:
            context.status_code = 200
            context.headers["content-type"] = artifact.mime_type
            buf = BytesIO(initial_bytes=artifact.content)
            return buf
        else:
            context.status_code = 404
        return None

    def add_artifact(self, artifact: Artifact):
        artifact.parent = self
        self.artifacts.append(artifact)

    def add_archive_artifact(self, filename: str, filecontent: bytes):
        artifact = Artifact(file_type="archive",
                            filename="artifacts.zip",
                            file_format="zip")
        artifact.content = make_zipfile_buffer(filename, filecontent)
        self.add_artifact(artifact)

    def add_trace_artifact(self, content: bytes):
        artifact = Artifact(file_type="trace",
                            filename="job.log",
                            file_format="raw")
        artifact.content = content
        self.add_artifact(artifact)


class MockServer:
    def __init__(self, mocker: Mocker, hostname: str):
        url = f"https://{hostname}"
        server = Server(url=url, mocker=mocker)
        self._server = server
        self.hostname = hostname
        self.next_id = random.randint(3, 888)
        server.mocker.head(url, text="<html></html>")

    def get_id(self):
        claim = self.next_id
        self.next_id += 1
        return claim

    @property
    def server(self) -> Server:
        return self._server

    def setup(self,
              group_path="mygroup",
              project_path="myproject",
              jobnames=None,
              ) -> Project:
        if jobnames is None:
            jobnames = ["job1", "job2"]

        grp = self.server.add_group(
            Group(ident=self.get_id(),
                  name=group_path.title(),
                  path=group_path))
        project = grp.add_project(
            Project(ident=self.get_id(),
                    path=project_path)
        )
        project.setup()
        pipeline = project.add_pipeline(
            Pipeline(ident=self.get_id(),
                     iid=self.get_id())
        )
        for name in jobnames:
            pipeline.add_job(
                Job(ident=self.get_id(),
                    name=name)
            )

        simple_path = f"{self.hostname}/{project.path_with_namespace}/{pipeline.id}"
        for job in pipeline.jobs:
            # add an artifacts archive
            job.add_archive_artifact(
                f"artifact.{job.name}.txt",
                f"artifact from {job.name} from {simple_path}".encode()
            )
            # add a log
            job.add_trace_artifact(
                f"job trace from {job.name} from {simple_path}".encode())

        return project


def make_zipfile_buffer(filename: str, content: bytes) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as fd:
        fd.writestr(filename, content)
    return buf.getvalue()
