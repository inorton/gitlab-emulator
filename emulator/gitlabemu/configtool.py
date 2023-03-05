"""
Configure gitlab emulator context, servers, local variables and docker bind mounts
"""
from argparse import ArgumentParser, Namespace

from . import configtool_ctx
from . import configtool_gitlab
from . import configtool_runner
from . import configtool_vars
from . import configtool_volumes
from .userconfig import get_user_config

GLOBAL_DESC = __doc__


def win_shell_cmd(opts: Namespace):
    cfg = get_user_config()
    current = cfg.current_context
    if opts.cmd or opts.powershell:
        if opts.cmd:
            cfg.contexts[current].windows.cmd = True
        elif opts.powershell:
            cfg.contexts[current].windows.cmd = False
        cfg.save()

    if cfg.contexts[current].windows.cmd:
        print("Windows shell is cmd")
    else:
        print("Windows shell is powershell")


def main(args=None):
    parser = ArgumentParser(description=GLOBAL_DESC)
    subparsers = parser.add_subparsers()
    configtool_ctx.setup_cmd(subparsers)
    configtool_gitlab.setup_cmd(subparsers)
    configtool_vars.setup_cmd(subparsers)
    configtool_volumes.setup_cmd(subparsers)
    configtool_runner.setup_cmd(subparsers)

    # might remove this feature
    win_shell = subparsers.add_parser("windows-shell", help="Set the global shell for windows jobs (default is powershell)")
    win_shell_grp = win_shell.add_mutually_exclusive_group()
    win_shell_grp.add_argument("--cmd", default=False, action="store_true",
                               help="Use cmd for jobs")
    win_shell_grp.add_argument("--powershell", default=False, action="store_true",
                               help="Use powershell for jobs (default)")
    win_shell.set_defaults(func=win_shell_cmd)

    opts = parser.parse_args(args)
    if hasattr(opts, "func"):
        opts.func(opts)
    else:
        parser.print_usage()


if __name__ == "__main__":
    main()
