import os
from typing import Optional, Dict, List
from gitlab import GitlabGetError

from .generator import (generate_pipeline_yaml,
                        generate_artifact_fetch_job,
                        create_pipeline_branch,
                        wait_for_project_commit_pipeline)
from .gitlab.types import RESERVED_TOP_KEYS
from .gitlab_client_api import parse_gitlab_from_arg, get_current_project_client, do_gitlab_fetch
from .helpers import note, die, git_current_branch
from .logmsg import info
from .yamlloader import ordered_dump


def print_pipeline_jobs(pipeline,
                        status: Optional[bool] = False,
                        completed: Optional[bool] = False):
    """print the jobs in the pipeline"""
    jobs = list(pipeline.jobs.list(all=True))
    if completed:
        jobs = [x for x in jobs if x.status == "success"]
        note(f"Listing completed jobs in {pipeline.web_url}")
    else:
        note(f"Listing jobs in {pipeline.web_url}")
    jobdict = {}
    for x in jobs:
        jobdict[x.name] = x
    names = sorted([x.name for x in jobs])

    if status:
        note(f"{'Name':48} Status")

    for name in names:
        if status:
            print(f"{name:48} {jobdict[name].status}", flush=True)
        else:
            print(name, flush=True)


def pipelines_cmd(tls_verify: Optional[bool] = True,
                  matchers: Optional[Dict[str, str]] = None,
                  do_list: Optional[bool] = False,
                  do_cancel: Optional[bool] = False,
                  limit: Optional[int] = 10,
                  ):
    """List/Cancel/Generate pipelines"""
    client, project, _ = get_current_project_client(tls_verify=tls_verify, need_remote=False)
    if not matchers:
        matchers = {}

    if do_list or do_cancel:
        if do_list:
            matching = ""
            if matchers:
                matching = f"matching {matchers}"
            note(f"Recent pipelines from project '{project.path_with_namespace}' on {client.api_url} {matching}")
        elif do_cancel:
            note(f"Cancel pipelines in project '{project.path_with_namespace}' on {client.api_url} matching: {matchers}")
        page = 1
        seen = 0
        pagesize = 10
        if do_list:
            print(f"{'# ID':<12} {'Status':<8} {'Commit':<40} Git Ref", flush=True)
        while seen < limit:
            pipes = project.pipelines.list(sort="desc", order_by="updated_at", page=page, per_page=pagesize, **matchers)
            if not pipes:
                break
            for pipe in pipes:
                if seen >= limit:
                    break
                if do_list:
                    print(f"{pipe.id:>12} {pipe.status:<8} {pipe.sha} {pipe.ref}")
                elif do_cancel:
                    print(f"Cancelling {pipe.id:>12} {pipe.status:<8} {pipe.sha} {pipe.ref}")
                    pipe.cancel()
                seen += 1
            if len(pipes) == pagesize:
                page += 1


def create_pipeline(vars: Optional[Dict[str, str]] = None,
                    tls_verify: Optional[bool] = True):
    """Trigger a pipeline on the current branch if possible"""
    cwd = os.getcwd()
    client, project, remotename = get_current_project_client(tls_verify=tls_verify)
    branch = git_current_branch(cwd)
    note(f"Creating pipeline for {branch} ..")
    started = project.pipelines.create(data={"ref": branch, "variables": vars})
    if started:
        note(f"Created pipeline {started.id} with ref={started.ref} at commit {started.sha}")
        note(started.web_url)


def generate_partial_pipeline(loader, *goals, variables: Optional[Dict[str, str]] = None):
    if not goals:
        die("Cannot generate a pipeline with zero jobs")



def generate_pipeline(loader, *goals,
                      variables: Optional[Dict[str, str]] = None,
                      use_from: Optional[str] = None,
                      dump_only: Optional[bool] = False,
                      tls_verify: Optional[bool] = True) -> Optional[dict]:
    """Generate and push a subset pipeline"""
    pipeline = None
    download_jobs = {}
    deps = {}
    client, project, remotename = get_current_project_client(tls_verify=tls_verify)
    cwd = os.getcwd()
    if not goals:
        die("Cannot generate a pipeline with zero jobs")

    note(f"Generate subset pipeline to build '{goals}'..")
    recurse = True
    if use_from:
        recurse = False
        ident = parse_gitlab_from_arg(use_from, prefer_gitref=True)
        if ident.pipeline:
            note(f"Checking source pipeline {ident.pipeline} ..")
            try:
                pipeline = project.pipelines.get(ident.pipeline)
            except GitlabGetError as err:
                die(f"Failed to read pipeline {ident.pipeline}, {err.error_message}")
        elif ident.gitref:
            note(f"Searching for latest pipeline on {ident.gitref} ..")
            # find the newest pipeline for this git reference
            found = project.pipelines.list(
                sort="desc",
                ref=ident.gitref,
                order_by="updated_at",
                page=1, per_page=5,
                status='success')
            if not found:
                die(f"Could not find a completed pipeline for git reference {ident.gitref}")
            pipeline = found[0]
        else:
            die(f"Cannot work out pipeline --from {use_from}")

        # now make sure the pipeline contains the jobs we need
        pipeline_jobs = {}

        for item in pipeline.jobs.list(all=True):
            if item.status == "success":
                pipeline_jobs[item.name] = item

        for goal in goals:
            loaded = loader.load_job(goal)
            if loaded.check_skipped():
                info(f"{goal} skipped by rules")
                continue

            for dep in loaded.dependencies:
                if dep in goals:
                    continue
                if dep not in pipeline_jobs:
                    die(f"Pipeline did not contain a successful '{dep}' job needed by {goal}")
                else:
                    from_job = pipeline_jobs[dep]
                    if hasattr(from_job, "artifacts"):  # missing if it created no artifacts
                        archives = [x for x in from_job.artifacts if x["file_type"] == "archive"]
                        if archives:
                            artifact_url = f"{client.api_url}/projects/{project.id}/jobs/{from_job.id}/artifacts"
                            download_jobs[dep] = artifact_url
                            if goal not in deps:
                                deps[goal] = []
                            deps[goal].append(dep)

    generated = generate_pipeline_yaml(loader, *goals, recurse=recurse)
    jobs = [name for name in generated.keys() if name not in RESERVED_TOP_KEYS]
    note(f"Will build jobs: {jobs} ..")
    stages = generated.get("stages", ["test"])

    for from_name in download_jobs:
        fetch_job = generate_artifact_fetch_job(loader,
                                                stages[0],
                                                {from_name: download_jobs[from_name]},
                                                tls_verify=client.ssl_verify)
        generated[from_name] = fetch_job

    for varname in variables:
        generated["variables"][varname] = variables[varname]

    if dump_only:
        return generated

    branch_name = generate_subset_branch_name(client, cwd)
    note(f"Creating temporary pipeline branch '{branch_name}'..")
    commit = create_pipeline_branch(cwd,
                                    remotename,
                                    branch_name,
                                    f"subset pipeline for {goals}",
                                    {
                                        ".gitlab-ci.yml": ordered_dump(generated)
                                    })
    if commit:
        note(f"Custom build commit is {commit}")
        note(f"Waiting for new pipeline to start..")
        pipeline = wait_for_project_commit_pipeline(project, commit)
        if not pipeline:
            die("Could not find the pipeline for our change")
        else:
            note(f"Building: {pipeline.web_url}")

    else:
        die("Could not make a custom pipeline branch, "
            "please make sure your local changes are committed first")


def get_subset_prefix() -> str:
    return "temp/"

def generate_subset_branch_name(client, cwd):
    """Get the subset name of the current branch"""
    branch_name = f"{get_subset_prefix()}{client.user.username}/{git_current_branch(cwd)}"
    return branch_name


def export_cmd(pipeline: str, outdir: str, *jobs, tls_verify: Optional[bool] = True, exec_export: Optional[List[str]] = None):
    do_gitlab_fetch(pipeline,
                    [x for x in jobs],
                    tls_verify=tls_verify,
                    callback=exec_export,
                    export_to=outdir)
