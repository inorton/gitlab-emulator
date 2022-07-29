"""List job status in a pipeline"""
import os
from argparse import Namespace, ArgumentParser

from gitlab import GitlabGetError

from ..helpers import note, die
from .subcommand import Command
from ..gitlab_client_api import get_current_project_client
from ..pipelines import print_pipeline_jobs
from ..helpers import git_current_branch


class JobListCommand(Command):
    """List pipeline jobs"""
    name = "jobs"
    description = __doc__

    def setup(self, parser: ArgumentParser) -> None:
        parser.add_argument("PIPELINE", type=int, default=None, nargs="?",
                            help="The pipeline number to fetch, defaults to the last on this branch")

    def run(self, opts: Namespace):
        cwd = os.getcwd()
        client, project, _ = get_current_project_client(tls_verify=opts.tls_verify)

        if opts.PIPELINE is None:
            branch = git_current_branch(cwd)
            note(f"Searching for most recent pipeline on branch: {branch} ..")
            pipes = list(project.pipelines.list(sort="desc", order_by="updated_at", pagesize=1, page=1, ref=branch))
            if not pipes:
                die(f"Could not find any pipelines for ref={branch}")
            pipeline = pipes[0]
        else:
            try:
                pipeline = project.pipelines.get(opts.PIPELINE)
            except GitlabGetError:
                die(f"Could not find pipeline {opts.PIPELINE}")

        print_pipeline_jobs(pipeline, status=True)
