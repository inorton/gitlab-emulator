"""Generate partial gitlab pipelines using temporary branches"""
import os
import sys
from argparse import ArgumentParser, Namespace

from .subcommand import MatcherCommand
from .types import NameValuePair
from .. import configloader
from ..gitlab_client_api import get_current_project_client
from ..helpers import die
from ..pipelines import generate_pipeline, generate_subset_branch_name, get_subset_prefix, pipelines_cmd
from ..yamlloader import ordered_dump


class SubsetCommand(MatcherCommand):
    name = "subset"
    description = __doc__

    def setup(self, parser: ArgumentParser) -> None:
        super(SubsetCommand, self).setup(parser)
        parser.add_argument("JOB", nargs="*",
                            type=str,
                            default=[],
                            help="Generate a temporary pipeline including JOB (may be repeated)")
        parser.add_argument("-e",
                            dest="variables",
                            default=[],
                            action="append",
                            metavar="NAME=VALUE",
                            type=NameValuePair,
                            help="Add a pipeline variable")
        parser.add_argument("--from",
                            dest="FROM",
                            type=str,
                            metavar="PIPELINE",
                            help="Re-use artifacts from a pipeline")
        parser.add_argument("--branches",
                            default=False, action="store_true",
                            help="List subset branch names (see also --match)")
        parser.add_argument("--dump", type=str,
                            help="Dump the generated pipeline to a file instead of running")
        parser.add_argument("--clean",
                            default=False, action="store_true",
                            help="Delete leftover subset branches from the gitlab repo")

    def run(self, opts: Namespace):
        variables = {}
        for item in opts.variables:
            variables[item.name] = item.value
        jobs = opts.JOB
        # only allow clean if there are no jobs
        if jobs:
            if opts.clean or opts.match:
                die("Cannot --clean or --match and run a build at the same time")
        else:
            if opts.FROM:
                die("--from requires one or more jobs")

        if len(jobs):
            fullpath = os.path.abspath(configloader.find_ci_config(os.getcwd()))
            loader = configloader.Loader(emulator_variables=False)
            loader.load(fullpath)
            # generate a subset pipeline
            result = generate_pipeline(loader, *jobs, variables=variables,
                                       dump_only=opts.dump is not None,
                                       use_from=opts.FROM,
                                       tls_verify=opts.tls_verify)
            if opts.dump:
                print(f"Saving generated pipeline as: {opts.dump}", file=sys.stderr)
                with open(opts.dump, "w") as dumpcfg:
                    dumpcfg.write(ordered_dump(result))
        else:
            client, project, remotename = get_current_project_client(tls_verify=opts.tls_verify)

            reference = generate_subset_branch_name(client, os.getcwd())
            match = {}
            if opts.match:
                if opts.match[0].name == "ref":
                    reference = f"{get_subset_prefix()}{opts.match[0].value}"
            match["ref"] = reference
            if opts.clean or opts.branches:
                search = f"^{reference}"
                if opts.branches:
                    # search for all subsets
                    search = f"^{get_subset_prefix()}"
                branches = project.branches.list(search=search, all=True)
                if search:
                    if not opts.branches:
                        branches = [x for x in branches if x.name == reference]
                branches = [x for x in branches if x.commit.get("title", "").startswith("subset pipeline for ")]
                if opts.clean:
                    for branch in branches:
                        # if the branch isn't running
                        pipelines = project.pipelines.list(ref=branch.commit.get("id"), all=True)
                        if not pipelines:
                            print(f"Deleting branch: {branch.name} ", flush=True)
                            branch.delete()
                        else:
                            print(f"Not cleaning, branch '{branch.name}' is currently running a pipeline")
                else:
                    for branch in branches:
                        print(branch.name)
            else:
                # print pipelines for this branch:
                pipelines_cmd(tls_verify=opts.tls_verify,
                              matchers=match,
                              limit=opts.limit,
                              do_list=True)
