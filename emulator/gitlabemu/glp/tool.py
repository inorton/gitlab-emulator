"""Gitlab Pipeline Tool"""
from typing import Optional, List
from .subcommand import ArgumentParserEx
from .buildtool import BuildCommand
from .canceltool import CancelCommand
from .exporttool import ExportCommand
from .jobstool import JobListCommand
from .listtool import ListCommand
from .subsettool import SubsetCommand


parser = ArgumentParserEx(description=__doc__)
parser.add_argument("--insecure", "-k", dest="tls_verify",
                    default=True, action="store_false",
                    help="Turn off SSL/TLS cert validation")
parser.add_subcommand(BuildCommand())
parser.add_subcommand(CancelCommand())
parser.add_subcommand(ExportCommand())
parser.add_subcommand(JobListCommand())
parser.add_subcommand(ListCommand())
parser.add_subcommand(SubsetCommand())


def run(args: Optional[List[str]] = None) -> None:
    opts = parser.parse_args(args)
    opts.func(opts)
