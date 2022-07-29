"""Start gitlab pipelines"""
from argparse import ArgumentParser, Namespace
from .subcommand import Command
from .types import NameValuePair
from ..pipelines import create_pipeline


class BuildCommand(Command):
    name = "build"
    description = __doc__

    def setup(self, parser: ArgumentParser) -> None:
        parser.add_argument("-e",
                            dest="variables",
                            default=[],
                            action="append",
                            metavar="NAME=VALUE",
                            type=NameValuePair,
                            help="Add a pipeline variable")

    def run(self, opts: Namespace):
        vars = {}
        for item in opts.variables:
            vars[item.name] = item.value
        # create a pipeline for the current branch
        create_pipeline(vars=vars, tls_verify=opts.tls_verify)
