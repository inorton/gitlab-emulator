"""Cancel running gitlab project pipelines"""
from argparse import Namespace

from .subcommand import MatcherCommand
from ..pipelines import pipelines_cmd


class CancelCommand(MatcherCommand):
    """Cancel pipelines"""
    name = "cancel"
    description = __doc__

    def run(self, opts: Namespace):
        matchers = {}
        for item in opts.match:
            matchers[item.name] = item.value

        pipelines_cmd(matchers=matchers,
                      limit=opts.limit,
                      tls_verify=opts.tls_verify,
                      do_cancel=True)
