"""
The main logic for polling, executing and reporting jobs
"""
import os
import platform
import tempfile
import shutil
from .common import ZipFileEx
from .httpclient import Session
from .consts import NAME, VERSION
from requests_toolbelt.multipart import encoder


class Runner(Session):
    """
    The Python Gitlab Runner
    """

    def __init__(self, server, token):
        """
        Start a runner
        :param server: The gitlab server
        :param token: The runner access token (not the registration token)
        """
        super(Runner, self).__init__()
        self.server = server
        self.builds = os.getcwd()
        self.token = token
        self.api_prefix = "{}/api/v4".format(self.server)
        self.executor = "shell"
        self.shell = "bash"
        if platform.system() == "Windows":
            self.shell = "cmd"

        self.image = False
        self.services = False

    def features(self):
        """
        Get the features this runner is enabled with
        :return:
        """
        return {
            "variables": True,
            "artifacts": True,
            "artifacts_exclude": True,
            "cache": False,
            "shared": True,
            "upload_multiple_artifacts": True,
            "session": True,
            "terminal": True,
            "image": self.image,  # set True for docker later
            "services": self.services,
        }

    def api(self, name):
        """
        Return the named API endpoint
        :param name:
        :return:
        """
        return "{}/{}".format(self.api_prefix, name)

    def register(self, desc, regtoken, tags=["gitlab-python-runner_added"]):
        """
        Register this runner with the server
        :param desc: The description for this new runner
        :param regtoken: The runner registration token
        :param tags: set these runner tags
        :return:
        """
        resp = self.post(self.api("runners"), data={
            "token": regtoken,
            "description": desc,
            "run_untagged": False,
            "tag_list": tags
        })

        resp.raise_for_status()

        result = self.json(resp)

        self.token = result.get("token", None)

        assert self.token, "Bug? Failed to register, no token found!"

    def unregister(self, token=None):
        """
        Delete a registered runner
        :param token:
        :return:
        """
        if token:
            self.token = token

        resp = self.delete(self.api("runners"), data={
            "token": self.token
        })

        resp.raise_for_status()

        self.token = None

    def get_info(self):
        """
        Return the info dict
        :return:
        """
        opsys = platform.system().lower()

        cpu = platform.machine()

        if cpu == "x86_64":
            cpu = "amd64"

        return {
            "name": NAME,
            "version": VERSION,
            "revision": VERSION,
            "platform": opsys,
            "architecture": cpu,
            "executor": self.executor,
            "shell": self.shell,
            "features": self.features(),
        }

    def poll(self):
        """
        Ask gitlab if there are any jobs we can run
        :return:
        """
        resp = self.post(self.api("jobs/request"), json={
            "info": self.get_info(),
            "token": self.token,
        })
        resp.raise_for_status()
        if resp.status_code == 201:
            # we have been given a job!
            return self.json(resp)

        return None

    def trace(self, trace, text, offset=0):
        """
        Upload some trace
        :param trace:
        :param text:
        :param offset:
        :return:
        """
        job = trace.job
        resp = self.patch(self.api("jobs/{}/trace".format(job["id"])),
                          headers={
                              "Content-Type": "text/plain",
                              "Content-Length": str(len(text)),
                              "Content-Range": "{}-{}".format(offset, offset + len(text)),
                              "Job-Token": job["token"]},
                          data=text)
        resp.raise_for_status()

        return offset + len(text)

    def success(self, job):
        """
        Report success
        :param job:
        :return:
        """
        resp = self.put(self.api("jobs/{}".format(job["id"])), json={
            "info": self.get_info(),
            "token": job["token"],
            "state": "success",
        })

        resp.raise_for_status()

    def failed(self, job):
        """
        Report failure
        :param job:
        :return:
        """
        resp = self.put(self.api("jobs/{}".format(job["id"])), json={
            "info": self.get_info(),
            "token": job["token"],
            "state": "failed",
        })
        resp.raise_for_status()

    def get_dependencies(self, trace, job, build_dir):
        """
        Get the dependencies for the given job
        :param trace: trace
        :param job: gitlab job object
        :param build_dir: Place to unpack artifacts into
        :return:
        """
        for other in job["dependencies"]:
            if "artifacts_file" not in other:  # other job did not save any artifacts
                continue
            trace.writeline("Fetching artifacts from {}..".format(other["name"]))
            url = self.api("jobs/{}/artifacts".format(other["id"]))
            resp = self.get(url,
                            stream=True,
                            headers={
                                "Job-Token": other["token"],
                            })
            resp.raise_for_status()
            try:
                tmpdir = tempfile.mkdtemp()
                path = os.path.join(tmpdir, other["artifacts_file"]["filename"])
                with open(path, 'wb') as f:
                    resp.raw.decode_content = True
                    shutil.copyfileobj(resp.raw, f)
                self.unpack_dependencies(trace, path, build_dir)
            finally:
                shutil.rmtree(tmpdir)

    def unpack_dependencies(self, trace, archive_file, build_dir):
        """
        Extract a downloaded artifact into the build tree
        :param trace:
        :param archive_file:
        :param build_dir:
        :return:
        """
        if self.features().get("artifacts", False):
            try:
                tmpdir = tempfile.mkdtemp()
                with ZipFileEx(archive_file, mode="r") as zf:
                    trace.writeline("Unpacking artifacts into {}..".format(build_dir))
                    zf.extractall(path=build_dir)
            finally:
                shutil.rmtree(tmpdir)

    def upload(self, trace, job, archive_file):
        """
        Upload artifacts from a job
        :param trace:
        :param job:
        :param archive_file:
        :return:
        """
        url = self.api("jobs/{}/artifacts".format(job["id"]))
        trace.writeline("Uploading artifacts to gitlab..")
        with open(archive_file, "rb") as archive:
            # solution to large uploads
            # lifted from https://stackoverflow.com/questions/35779879/python-requests-upload-large-file-with-additional-data
            form = encoder.MultipartEncoder({
                "file": (os.path.basename(archive_file), archive, "application/octet-stream"),
                "artifact_format": "zip",
                "artifact_type": "archive"
            })
            headers = {
                       "Content-Type": form.content_type,
                       "Job-Token": job["token"]
                       }
            resp = self.post(url,
                             headers=headers,
                             data=form)
        resp.raise_for_status()
        trace.writeline("Upload complete")


class DockerRunner(Runner):
    """
    Docker Enabled mode
    """
    def __init__(self, server, token):
        super(DockerRunner, self).__init__(server, token)
        self.image = True
        self.services = True
