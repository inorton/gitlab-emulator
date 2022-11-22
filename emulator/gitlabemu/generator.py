"""Generate sub-pipelines"""
import os.path
import subprocess
import time
from typing import List, Dict, Optional

from gitlab.v4.objects import ProjectPipeline
from .yamlloader import StringableOrderedDict
from .configloader import Loader
from .helpers import git_top_level, git_commit_sha, git_uncommitted_changes, git_current_branch, git_push_force_upstream


def generate_artifact_fetch_job(
        loader: Loader,
        stage: str,
        needed: Dict[str, str],
        tls_verify: Optional[bool] = True
) -> dict:
    """Generate a job to fetch artifacts of needed jobs from a completed pipeline"""
    # use CI_JOB_TOKEN to fetch the artifacts
    script = []
    paths = []
    generated = {}
    verify = "--cacert $CI_SERVER_TLS_CA_FILE"
    if not tls_verify:
        verify = "--insecure"
    for name in needed:
        job = loader.get_job(name)
        # does it define any artifacts?
        artifacts = job.get("artifacts", {})
        artifact_paths = artifacts.get("paths", [])
        if artifact_paths:
            url = needed[name]
            script.extend(
                [
                    'apk add curl',
                    f'curl {verify} --location --output {name}-artifacts.zip --header "JOB-TOKEN: $CI_JOB_TOKEN" {url}',
                    f'unzip -o {name}-artifacts.zip',
                    f'rm -f {name}-artifacts.zip',
                ]
            )

            paths.extend(artifact_paths)
    if paths:
        generated = {
            "stage": stage,
            "image": "alpine:3.14",
            "script": script,
            "artifacts": {
                "paths": list(set(paths)),
                "expire_in": '1 day'
            },
            "variables": {
                "KUBERNETES_CPU_REQUEST": "1",
                "KUBERNETES_MEMORY_REQUEST": "2G",
            }
        }

    return generated


def generate_pipeline_yaml(loader: Loader,
                           *goals: str,
                           recurse: Optional[bool] = True) -> dict:
    """Generate a subset pipeline to build the given goals"""
    generated = StringableOrderedDict()
    stages = loader.config.get("stages", [])
    needed = set(goals)

    while len(needed):
        for name in list(needed):
            needed.remove(name)
            job = loader.get_job(name)
            # strip out extends and rules
            for remove in ["extends", "when", "only", "rules", "except"]:
                if remove in job:
                    del job[remove]
            stage = job.get("stage", None)
            if stage:
                if stage not in stages:
                    stages.append(stage)
            generated[name] = job
            loaded = loader.load_job(name)
            if recurse:
                # build the needed jobs in the pipeline
                for item in loaded.dependencies:
                    if isinstance(item, str):
                        needed.add(item)

    if stages:
        generated["stages"] = list(stages)

    # get the variables and defaults sections etc
    variables = dict(loader.config.get("variables", {}))
    generated["variables"] = variables
    for item in ["image", "default", "before_script", "after_script", "services"]:
        if item in loader.config:
            generated[item] = loader.config.get(item)

    return generated


def create_pipeline_branch(repo: str,
                           remote: str,
                           new_branch: str,
                           commit_message: str,
                           files: Dict[str, str],
                           ) -> Optional[str]:
    """"""
    commit = None
    topdir = git_top_level(repo)
    original = git_current_branch(topdir)
    changes = git_uncommitted_changes(topdir)
    if not changes:
        try:
            subprocess.check_call(["git", "-C", topdir, "checkout", "-B", new_branch])
            for filename in files:
                filepath = os.path.join(topdir, filename)
                folder = os.path.dirname(filepath)
                if not os.path.exists(folder):
                    os.makedirs(folder)
                with open(filepath, "w") as fd:
                    fd.write(files[filename])
                subprocess.check_call(["git", "-C", topdir, "add", filepath])

            subprocess.check_call(["git", "-C", topdir, "commit", "-am", commit_message])
            git_push_force_upstream(topdir, remote, new_branch)
            commit = git_commit_sha(topdir)
        finally:
            subprocess.check_call(["git", "-C", topdir, "checkout", "-qf", original])
    return commit


def wait_for_project_commit_pipeline(project, commit, timeout=30) -> Optional[ProjectPipeline]:
    started = time.time()
    while time.time() - started < timeout:
        time.sleep(2)
        pipes = project.pipelines.list(sort="desc", order_by="updated_at", page=1, per_page=16)
        for pipeline in pipes:
            if pipeline.sha == commit:
                return pipeline
    return None
