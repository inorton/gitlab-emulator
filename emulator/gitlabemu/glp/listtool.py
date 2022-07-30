"""List gitlab project pipelines"""
from argparse import Namespace

from .subcommand import MatcherCommand
from ..pipelines import pipelines_cmd


class ListCommand(MatcherCommand):
    """List pipelines"""
    name = "list"
    description = __doc__

    def run(self, opts: Namespace):
        matchers = {}
        for item in opts.match:
            matchers[item.name] = item.value

        pipelines_cmd(matchers=matchers,
                      limit=opts.limit,
                      tls_verify=opts.tls_verify,
                      do_list=True)
