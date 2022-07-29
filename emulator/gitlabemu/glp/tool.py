"""Gitlab Pipeline Tool"""
import sys
from typing import Optional, List
from .subcommand import ArgumentParserEx
from .listtool import ListCommand
from .canceltool import CancelCommand
from .buildtool import BuildCommand
from .subsettool import BuildSubsetCommand

parser = ArgumentParserEx(description=__doc__)
parser.add_argument("--insecure", "-k", dest="tls_verify",
                    default=True, action="store_false",
                    help="Turn off SSL/TLS cert validation")
parser.add_subcommand(ListCommand())
parser.add_subcommand(CancelCommand())
parser.add_subcommand(BuildCommand())
parser.add_subcommand(BuildSubsetCommand())


def run(args: Optional[List[str]] = None) -> None:
    opts = parser.parse_args(args)
    opts.func(opts)
