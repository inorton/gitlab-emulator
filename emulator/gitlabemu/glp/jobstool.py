"""List job status in a pipeline"""
import os
from argparse import Namespace, ArgumentParser

from ..helpers import note, die
from .subcommand import Command
from ..gitlab_client_api import get_current_project_client, find_project_pipeline
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
        client, project, _ = get_current_project_client(tls_verify=opts.tls_verify, need_remote=False)
        branch = None
        if opts.PIPELINE is None:
            branch = git_current_branch(cwd)
            note(f"Searching for most recent pipeline on branch: {branch} ..")

        pipeline = find_project_pipeline(project, pipeline=opts.PIPELINE, ref=branch)
        print_pipeline_jobs(pipeline, status=True)
