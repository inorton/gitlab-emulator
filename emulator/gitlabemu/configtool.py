"""
Configure gitlab emulator context, servers, local variables and docker bind mounts
"""
import sys
from argparse import ArgumentParser, Namespace

from gitlabemu.helpers import sensitive_varname, trim_quotes, die
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


def gitlab_cmd(opts: Namespace):
    cfg = get_user_config()
    ctx = cfg.contexts[cfg.current_context]
    if not opts.NAME:
        # list
        for item in ctx.gitlab.servers:
            print(f"{item.name:32} {item.server}")
    else:
        matched = [x for x in ctx.gitlab.servers if x.name == opts.NAME]
        if len(matched):
            first = matched[0]
            if opts.token:
                first.token = opts.token
            first.tls_verify = opts.tls_verify
        else:
            # add a new one
            if opts.server and opts.token:
                ctx.gitlab.add(opts.NAME, opts.server, opts.token, opts.tls_verify)
            else:
                die("Adding a new gitlab server entry requires --server URL and --token TOKEN")
        cfg.save()


def main(args=None):
    parser = ArgumentParser(description=GLOBAL_DESC)
    subparsers = parser.add_subparsers()

    set_ctx = subparsers.add_parser("context", help="Show/select the current and available gle contexts")
    set_ctx.add_argument("NAME", type=str, help="Name of the context to use (or create)", nargs="?")
    set_ctx.add_argument("--remove", default=False, action="store_true",
                         help="Remove the context")
    set_ctx.set_defaults(func=set_context_cmd)

    gl_ctx = subparsers.add_parser("gitlab", help="Update remote gitlab configurations")
    gl_ctx.add_argument("NAME", type=str, help="Set the name", default=None, nargs="?")
    gl_ctx.add_argument("--server", type=str, help="Set the URL for a gitlab server",
                        default=None)
    gl_ctx.add_argument("--insecure", default=True, action="store_false", dest="tls_verify",
                        help="Disable TLS certificate verification for this server (default is to verify)")
    gl_ctx.add_argument("--token", type=str,
                        help="Set the gitlab API token (should have git and api write access for best use)")
    gl_ctx.set_defaults(func=gitlab_cmd)

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
