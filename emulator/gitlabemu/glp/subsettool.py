"""Generate partial gitlab pipelines using temporary branches"""
import os
from argparse import ArgumentParser, Namespace
from .subcommand import Command
from .types import NameValuePair
from .. import configloader
from ..pipelines import generate_pipeline


class SubsetCommand(Command):
    name = "subset"
    description = __doc__

    def setup(self, parser: ArgumentParser) -> None:
        parser.add_argument("JOB", nargs="+",
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

    def run(self, opts: Namespace):
        vars = {}
        for item in opts.variables:
            vars[item.name] = item.value
        jobs = opts.JOB
        fullpath = os.path.abspath(configloader.find_ci_config(os.getcwd()))
        loader = configloader.Loader(emulator_variables=False)
        loader.load(fullpath)

        # generate a subset pipeline
        generate_pipeline(loader, *jobs, variables=vars,
                          use_from=opts.FROM,
                          tls_verify=opts.tls_verify)
