"""Python runner for real gitlab jobs based on gitlab-emulator"""
import argparse
import os
import platform
import requests
import shutil
import subprocess
import tempfile
import time
import yaml
import zipfile
import gzip
from pathlib import Path
from typing import Optional, Dict

from .. import runner, logmsg, ansi
from ..jobs import Job


HEADER_JOB_TOKEN = "Job-Token"
HEADER_USER_AGENT = "User-Agent"
HEADER_CONTENT_LENGTH = "Content-Length"
HEADER_CONTENT_RANGE = "Content-Range"
HEADER_CONTENT_TYPE = "Content-Type"

USER_AGENT = f"gitlab-emulator runner {runner.get_version()}"
CONTENT_TYPE = "text/plain"


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers[HEADER_USER_AGENT] = USER_AGENT
    return session


def get_arch() -> str:
    mach = platform.machine()
    if mach == "x86_64":
        mach = "amd64"
    return mach


class TraceUploader:

    def __init__(self, api_url: str, job_token: str, job_num: str, on_error: callable):
        self.offset = 0
        self.api_url = api_url.rstrip("/")  # eg https://gitlab.com/api/v4/jobs/
        self.job_number = job_num   # eg 1234
        self.job_token = job_token
        self.session = get_session()
        self.session.headers[HEADER_JOB_TOKEN] = job_token
        self.on_error = on_error
        self.masked_strings = []
        self.masked_strings.append(self.job_token)
        self.buf = ""
        self.bufsize = 512

    @property
    def encoding(self) -> str:
        return "utf-8"

    def write(self, data):
        self.buf = self.buf + data
        if len(self.buf) > self.bufsize:
            self.flush()

    def writeline(self, line):
        self.write(line)
        self.write("\n")
        self.flush()

    def flush(self):
        if self.buf:
            self.send(self.buf)
            self.buf = ""

    def send(self, data):
        url = f"{self.api_url}/api/v4/jobs/{self.job_number}/trace"

        for masked in self.masked_strings:
            data = data.replace(masked, "******")

        size = len(data)

        resp = self.session.patch(
            url,
            headers={
                HEADER_CONTENT_TYPE: CONTENT_TYPE,
                HEADER_CONTENT_LENGTH: str(size),
                HEADER_CONTENT_RANGE: f"{self.offset}-{self.offset + size - 1}"
            },
            params={
                "debug_trace": "false",
            },
            data=data)
        self.offset += size
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            self.on_error()


class JobRunner:
    """Requests jobs from a gitlab server"""

    def __init__(self, api_url: str, runner_token: str):
        self.api_url = api_url.rstrip("/")
        self.runner_token = runner_token
        self.error = False
        self.tracer: Optional[TraceUploader] = None
        self.workdir = Path(os.getcwd())
        self.job_count = 0

    def server_error(self):
        self.error = True

    def make_job_request(self) -> dict:
        request = {
            "info": {
                "architecture": get_arch(),
                "config": {
                    "gpus": ""
                },
                "executor": "shell",
                "features": {
                    "artifacts": True,
                    "artifacts_exclude": True,
                    "cache": False,
                    "cancelable": True,
                    "fallback_cache_keys": True,
                    "image": False,
                    "masking": True,
                    "multi_build_steps": True,
                    "proxy": False,
                    "raw_variables": True,
                    "refspecs": True,
                    "return_exit_code": True,
                    "service_multiple_aliases": False,
                    "service_variables": False,
                    "services": False,
                    "session": False,
                    "shared": False,
                    "terminal": False,
                    "trace_checksum": False,
                    "trace_reset": True,
                    "trace_size": True,
                    "upload_multiple_artifacts": True,
                    "upload_raw_artifacts": True,
                    "variables": True,
                    "vault_secrets": False
                },
                "name": "gitlab-emulator python runner",
                "platform": platform.system().lower(),
                "shell": "bash",
                "version": "16.3.0"
            },
            "token": self.runner_token
        }
        return request

    def poll(self):
        session = get_session()
        request = self.make_job_request()

        resp = session.post(f"{self.api_url}/api/v4/jobs/request", json=request)

        resp.raise_for_status()

        if resp.status_code == 201:
            self.run_job(resp, session)
        else:
            logmsg.info("no job")

    def run_job(self, job_request, session):
        # we have a job!
        self.job_count += 1
        job_data = job_request.json()
        logmsg.info(f"got a job id={job_data['id']}")
        job = Job()
        self.tracer = TraceUploader(self.api_url,
                                    job_token=job_data["token"],
                                    job_num=job_data["id"],
                                    on_error=self.server_error)
        job.stdout = self.tracer
        job.name = job_data["job_info"]["name"]
        # set vars
        for var in job_data["variables"]:
            job.configure_job_variable(var["key"], var["value"], force=True)
            if var["masked"]:
                self.tracer.masked_strings.append(var["value"])
        for step in job_data["steps"]:
            if step.get("name") == "script":
                job.script = step["script"]
                timeout = step.get("timeout", None)
                if timeout is not None:
                    job.timeout_seconds = int(timeout)
            elif step.get("name") == "after_script":
                job.after_script = step["script"]
        self.runner_info_msg(f"{USER_AGENT} on {platform.node()} {platform.uname()}")
        self.runner_info_msg("starting git clone..")
        workspace = self.git_clone(job_data["git_info"]["repo_url"],
                                   job_data["job_info"]["project_name"],
                                   job_data["git_info"]["sha"])
        failed = True
        try:
            job.workspace = str(workspace)
            job.configure_job_variable("CI_BUILDS_DIR", os.path.dirname(workspace.parent))
            self.runner_info_msg("starting job..")
            job.run()
            logmsg.info(f"job {job_data['id']} done")
            failed = False
        except Exception as err:
            logmsg.info(f"job {job_data['id']} failed: {err}")

        finally:
            # report status
            send = self.make_job_request()
            send["token"] = job_data['token']
            send["output"] = {"bytesize": self.tracer.offset + 1}
            if failed:
                send["state"] = "failed"
                self.runner_error_msg(f"job {send['state']}")
            else:
                send["state"] = "success"
                self.runner_info_msg(f"job {send['state']}")

            # do artifacts
            try:
                self.upload_job_artifacts(job_data, session, workspace)
                shutil.rmtree(workspace)

                session.put(f"{self.api_url}/api/v4/jobs/{job_data['id']}", json=send)
                time.sleep(1)
                # twice?
                session.put(f"{self.api_url}/api/v4/jobs/{job_data['id']}", json=send)
            except Exception as err:
                assert err
                import traceback
                send["state"] = "failed"

                self.runner_error_msg("runner failure")
                error = traceback.format_exc()
                self.runner_error_msg(error)
                logmsg.warning(error)

                session.put(f"{self.api_url}/api/v4/jobs/{job_data['id']}", json=send)

    def upload_job_artifacts(self, job_data, session, workspace):
        job_id = job_data['id']
        art_url = f"{self.api_url}/api/v4/jobs/{job_id}/artifacts"
        job_token = job_data['token']
        for arti in job_data["artifacts"]:
            art_type = arti.get("artifact_type")
            art_format = arti.get("artifact_format")
            art_name = arti.get("name")

            if art_name is None:
                art_name = "archive.zip"

            if art_format:
                temp_archives = Path(tempfile.mkdtemp(dir=self.workdir))
                local_file = temp_archives / (art_name + ".gz")
                try:
                    if art_type == "junit":
                        junit_files = []
                        for art_path in arti.get("paths", []):
                            junit_files.extend(list(workspace.rglob(art_path)))

                        with local_file.open("wb") as outfile:
                            for report in junit_files:
                                report_file = temp_archives / report.name
                                with gzip.GzipFile(report_file, "wb") as gz:
                                    gz.write(report.read_bytes())
                                outfile.write(report_file.read_bytes())

                        if len(junit_files):
                            self.post_artifact(session, local_file, art_format, local_file.name, art_type, art_url, job_token)

                    elif art_type == "archive":
                        with zipfile.ZipFile(local_file, mode="w") as zf:
                            for art_path in arti.get("paths", []):
                                matched_files = list(workspace.rglob(art_path))
                                self.runner_info_msg(
                                    f"artifacts: paths: - {art_path} matched {len(matched_files)} files in {workspace}")
                                for found in matched_files:
                                    rel_name = found.relative_to(workspace)
                                    zf.write(found, arcname=rel_name)

                        self.post_artifact(session, local_file, art_format, art_name, art_type, art_url, job_token)
                finally:
                    shutil.rmtree(temp_archives)

    def post_artifact(self, session, local_file, art_format, art_name, art_type, art_url, job_token):
        self.runner_info_msg(f"uploading {art_name} ..")
        job_request = session.post(
            art_url,
            headers={
                HEADER_USER_AGENT: USER_AGENT,
                HEADER_JOB_TOKEN: job_token,
            },
            params={
                "artifact_format": art_format,
                "artifact_type": art_type
            },
            files={
                "file": (art_name, local_file.open("rb"))
            }
        )
        job_request.raise_for_status()

    def git_clone(self, giturl: str, folder: str, checkout: str) -> Path:
        workdir = Path(tempfile.mkdtemp(dir=self.workdir))
        repo = workdir / folder
        repo.mkdir(parents=True)
        self.runner_info_msg(f"clone {giturl} into {workdir} ..")
        try:
            output = subprocess.check_output(["git", "clone", giturl, "."],
                                             encoding="utf-8",
                                             cwd=repo, stderr=subprocess.STDOUT)
            self.tracer.write(output)
            self.runner_info_msg(f"checkout {checkout} ..")
            output = subprocess.check_output(["git", "checkout", "-f", checkout],
                                             encoding="utf-8",
                                             cwd=repo, stderr=subprocess.STDOUT)
            self.tracer.write(output)
        except subprocess.CalledProcessError as cpe:
            self.tracer.write(cpe.output)
            raise

        return repo

    def runner_info_msg(self, msg):
        self.tracer.writeline(f"{ansi.ANSI_GREEN}{msg}{ansi.ANSI_RESET}")

    def runner_error_msg(self, msg):
        self.tracer.writeline(f"{ansi.ANSI_RED}{msg}{ansi.ANSI_RESET}")


class RunnerConfig:
    def __init__(self):
        self.builds_dir: Path = Path(os.getcwd()) / "builds"
        self.token: str = ""
        self.server: str = "https://gitlab.com"
        self.http_proxy: Optional[str] = None
        self.https_proxy: Optional[str] = None
        self.ca_cert: Optional[Path] = None
        self.poll_interval = 10
        self.max_jobs = -1

    def dump(self, filepath: Path):
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with filepath.open("w") as fd:
            data = {
                "builds_dir": str(self.builds_dir),
                "token": self.token,
                "server": self.server,
                "poll_interval": self.poll_interval,
                "max_jobs": self.max_jobs,
            }
            if self.ca_cert is not None:
                data["ca_cert"] = str(self.ca_cert)

            yaml.dump(data, fd, indent=2, sort_keys=True)

    def load(self, filepath: Path):
        with filepath.open("r") as fd:
            data = yaml.safe_load(fd)
        for name in ["token", "server", "http_proxy", "https_proxy", "max_jobs", "poll_interval"]:
            if name in data:
                value = data.get(name)
                setattr(self, name, value)
        for name in ["builds_dir", "ca_cert"]:
            if name in data:
                value = Path(data.get(name))
                setattr(self, name, value)

    def get_envs(self) -> Dict[str, str]:
        envs = {}
        if self.ca_cert:
            envs["REQUESTS_CA_BUNDLE"] = str(self.ca_cert.absolute())
            envs["GIT_SSL_CAINFO"] = str(self.ca_cert.absolute())

        if self.http_proxy:
            envs["HTTP_PROXY"] = self.http_proxy
        if self.https_proxy:
            envs["HTTPS_PROXY"] = self.https_proxy

        return envs


def run(args=None):
    opts = parser.parse_args(args)
    if opts.config is None:
        opts.config = Path(os.path.expanduser(os.path.join("~", "gitlab-py-runner.yml")))
    if hasattr(opts, "func"):
        opts.func(opts)
    else:
        parser.print_usage()


def command_run(opts: argparse.Namespace):
    if not opts.config.exists():
        logmsg.info(f"no such config: {opts.config}")

    cfg = RunnerConfig()
    cfg.load(opts.config)
    if opts.builds:
        cfg.builds_dir = opts.builds

    cfg.builds_dir.mkdir(parents=True, exist_ok=True)
    envs = cfg.get_envs()
    os.chdir(cfg.builds_dir)
    os.environ.update(envs)

    try:
        logmsg.FATAL_EXIT = False
        glr = JobRunner(cfg.server, cfg.token)

        while True:
            glr.poll()
            time.sleep(cfg.poll_interval)
            if cfg.max_jobs > 0:
                if glr.job_count >= cfg.max_jobs:
                    break
    finally:
        logmsg.FATAL_EXIT = True


def command_register(opts: argparse.Namespace):
    cfg = RunnerConfig()
    cfg.server = opts.server
    reg_token = opts.reg_token

    if reg_token:
        logmsg.info(f"register new runner on {cfg.server} ..")
        logmsg.info(f"with tags: {opts.tag_list} ")
        session = get_session()
        resp = session.post(
            f"{cfg.server}/api/v4/runners",
            data={
                "tag_list": opts.tag_list,
                "token": reg_token,
                "description": f"{USER_AGENT} on {platform.node()}"
            }
        )
        resp.raise_for_status()
        logmsg.info("registration complete")
        data = resp.json()
        cfg.token = data["token"]

    elif opts.token:
        logmsg.info(f"saving runner config")
        cfg.token = opts.token

    logmsg.info(f"saving config {opts.config}")
    cfg.dump(opts.config)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--config", "-c", help="Runner config file", metavar="CONFIG", type=Path)
parser.add_argument("--builds", "-C", help="Change to PATH before running jobs", metavar="PATH", type=Path)

subparsers = parser.add_subparsers(help="commands")

run_parser = subparsers.add_parser("run", help="Start the runner and poll for jobs")
run_parser.set_defaults(func=command_run)

reg_parser = subparsers.add_parser("register", help="Register this runner")
reg_parser.add_argument("--server", type=str, default="https://gitlab.com")
token_grp = reg_parser.add_mutually_exclusive_group()
token_grp.add_argument("--reg-token", type=str)
token_grp.add_argument("--token", type=str)
reg_parser.add_argument("--ca-cert", type=Path, help="Path to a custom CA cert")
reg_parser.add_argument("--https-proxy", type=str, help="Use a HTTP proxy")
reg_parser.add_argument("--tag-list", type=str, help="Set the tags the runner will use")
reg_parser.set_defaults(func=command_register)
