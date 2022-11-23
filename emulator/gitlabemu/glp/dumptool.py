"""Dump gitlab pipelines as a generic document"""
import sys

import yaml
from argparse import ArgumentParser, Namespace
from .subcommand import Command
from ..configloader import Loader, DEFAULT_CI_FILE
from ..genericci.types import GenericJob
from ..logmsg import info


class DumpCommand(Command):
    name = "dump"
    description = __doc__

    def setup(self, parser: ArgumentParser) -> None:
        parser.add_argument("-c", dest="cifile", type=str, default=DEFAULT_CI_FILE,
                            help="Load a specific CI file")
        parser.add_argument("JOB", type=str,
                            nargs="*",
                            help="Dump only one job")

    def run(self, opts: Namespace):
        loader = Loader()
        loader.load(opts.cifile)
        dump_jobs = loader.get_jobs()
        if opts.JOB:
            dump_jobs = [x for x in dump_jobs if x in opts.JOB]

        for jobname in dump_jobs:
            job = loader.load_job(jobname)
            generic = GenericJob()
            generic.from_job(loader, job)
            print(f"# job {jobname}")
            yaml.safe_dump(generic.to_dict(), stream=sys.stdout)


