"""Gitlab Pipeline Tool"""
import os
import sys
from argparse import ArgumentError
from typing import Optional, List

from .subcommand import ArgumentParserEx
from .buildtool import BuildCommand
from .canceltool import CancelCommand
from .dumptool import DumpCommand
from .exporttool import ExportCommand
from .jobstool import JobListCommand
from .listtool import ListCommand
from .subsettool import SubsetCommand
from ..gitlab_client_api import GITLAB_SERVER_ENV, GITLAB_PROJECT_ENV, posix_cert_fixup
from ..errors import ConfigLoaderError
from ..helpers import die


def override_server(server: str) -> str:
    if server:
        if "/" not in server:
            raise ArgumentError("--project should be HOST/GROUP/PROJECT")
        host, project = server.split("/", 1)
        os.environ[GITLAB_SERVER_ENV] = host
        os.environ[GITLAB_PROJECT_ENV] = project
        return server


parser = ArgumentParserEx(description=__doc__)
parser.add_argument("--project", type=override_server,
                    help="Use this gitlab project instead of the the current git repo, eg SERVER/GROUP/PROJECT")
parser.add_argument("--insecure", "-k", dest="tls_verify",
                    default=True, action="store_false",
                    help="Turn off SSL/TLS cert validation")
parser.add_subcommand(BuildCommand())
parser.add_subcommand(CancelCommand())
parser.add_subcommand(DumpCommand())
parser.add_subcommand(ExportCommand())
parser.add_subcommand(JobListCommand())
parser.add_subcommand(ListCommand())
parser.add_subcommand(SubsetCommand())


def top_level_usage(opts):
    parser.print_usage()
    sys.exit(1)


parser.set_defaults(func=top_level_usage)


def run(args: Optional[List[str]] = None) -> None:
    opts = parser.parse_args(args)
    try:
        with posix_cert_fixup():
            opts.func(opts)
    except ConfigLoaderError as err:
        die(str(err))
