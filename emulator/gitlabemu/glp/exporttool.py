"""Export pipelines"""
from argparse import ArgumentParser, Namespace
from .subcommand import Command
from ..pipelines import export_cmd


class ExportCommand(Command):
    name = "export"
    description = __doc__

    def setup(self, parser: ArgumentParser) -> None:
        parser.add_argument("PIPELINE", type=str,
                            help="Pipeline to export")
        parser.add_argument("SAVEDIR", type=str,
                            help="Save exported files to this folder")
        parser.add_argument("JOB", type=str, default=None,
                            nargs="*",
                            help="Limit export to only these named jobs")
        parser.add_argument("--exec", type=str, nargs="+",
                            default=None,
                            help="For each job exported, execute this process and substitute %%p for the job output folder")

    def run(self, opts: Namespace):
        jobs = []
        # allow use of --
        seen_exec = False
        exec_args = []
        for item in opts.JOB:
            if not seen_exec:
                if item in ["--exec"]:
                    seen_exec = True
                    continue
                jobs.append(item)
            else:
                exec_args.append(item)
        if seen_exec:
            opts.exec = exec_args

        export_cmd(opts.PIPELINE, opts.SAVEDIR, *jobs,
                   exec_export=opts.exec,
                   tls_verify=opts.tls_verify)
