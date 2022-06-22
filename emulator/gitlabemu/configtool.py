"""
Configure gitlab emulator context, servers, local variables and docker bind mounts
"""
import sys
from argparse import ArgumentParser, Namespace

from gitlabemu.helpers import sensitive_varname, trim_quotes
from gitlabemu.userconfigdata import UserContext, DEFAULT_CONTEXT
from .userconfig import get_user_config

GLOBAL_DESC = __doc__


def warning(text: str) -> None:
    print(f"warning: {text}", file=sys.stderr, flush=True)


def notice(text: str) -> None:
    print(f"notice: {text}", file=sys.stderr, flush=True)


def print_contexts():
    cfg = get_user_config()
    current = cfg.current_context
    for item in cfg.contexts:
        mark = " "
        if item == current:
            mark = "*"
        print(f"{mark} {item}")


def set_context_cmd(opts: Namespace):
    if opts.NAME is None:
        print_contexts()
    else:
        cfg = get_user_config()
        name = opts.NAME
        if opts.remove:
            if name in cfg.contexts:
                notice(f"delete context {name}")
                del cfg.contexts[name]
            if name == cfg.current_context:
                cfg.current_context = DEFAULT_CONTEXT
        else:
            cfg.current_context = name
            if name not in cfg.contexts:
                cfg.contexts[name] = UserContext()
        notice(f"gle context set to {cfg.current_context}")
        cfg.save()


def print_sensitive_vars(variables: dict) -> None:
    for name in sorted(variables.keys()):
        if sensitive_varname(name):
            print(f"{name}=************")
        else:
            print(f"{name}={variables[name]}")


def vars_cmd(opts: Namespace):
    cfg = get_user_config()
    current = cfg.current_context
    if opts.local:
        vars_container = cfg.contexts[current].local
    elif opts.docker:
        vars_container = cfg.contexts[current].docker
    else:
        vars_container = cfg.contexts[current]
    variables = vars_container.variables
    if opts.VAR is None:
        print_sensitive_vars(variables)
    elif "=" in opts.VAR:
        name, value = opts.VAR.split("=", 1)
        if not value:
            # unset variable if set
            if name in variables:
                notice(f"Unsetting {name}")
                del vars_container.variables[name]
            else:
                warning(f"{name} is not set. If you want an empty string, use {name}='\"\"'")
        else:
            notice(f"Setting {name}")
            vars_container.variables[name] = trim_quotes(value)

        cfg.save()
    else:
        if opts.VAR in variables:
            print_sensitive_vars({opts.VAR: variables[opts.VAR]})
        else:
            print(f"{opts.VAR} is not set")


def volumes_cmd(opts: Namespace):
    cfg = get_user_config()
    current = cfg.current_context

    if opts.add:
        cfg.contexts[current].docker.add_volume(opts.add)
        cfg.save()
    elif opts.remove:
        cfg.contexts[current].docker.remove_volume(opts.remove)
        cfg.save()

    for volume in cfg.contexts[current].docker.volumes:
        print(volume)


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

    set_ctx = subparsers.add_parser("context", help="Show/select the current and available gle contexts")
    set_ctx.add_argument("NAME", type=str, help="Name of the context to use (or create)", nargs="?")
    set_ctx.add_argument("--remove", default=False, action="store_true",
                         help="Remove the context")
    set_ctx.set_defaults(func=set_context_cmd)

    set_var = subparsers.add_parser("vars", help="Show/set environment variables injected into jobs")
    set_var.add_argument("--local", default=False, action="store_true",
                         help="Set/Show variables for local shell jobs only")
    set_var.add_argument("--docker", default=False, action="store_true",
                         help="Set/Show variables for local docker jobs only")
    set_var.add_argument("VAR", type=str, help="Set or unset an environment variable", nargs="?")
    set_var.set_defaults(func=vars_cmd)

    set_vols = subparsers.add_parser("volumes", help="Show/set the docker volumes")
    vol_grp = set_vols.add_mutually_exclusive_group()
    vol_grp.add_argument("--add", type=str, metavar="VOLUME",
                         help="Volume to add (eg /path/to/folder:/mount/path:rw)")
    vol_grp.add_argument("--remove", type=str, metavar="PATH",
                         help="Volume to remove (eg /mount/path)")
    set_vols.set_defaults(func=volumes_cmd)

    win_shell = subparsers.add_parser("windows-shell", help="Set the shell for windows jobs (default is powershell)")
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
