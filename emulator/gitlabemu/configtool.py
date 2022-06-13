"""
Configure gitlab emulator context, servers, local variables and docker bind mounts
"""
import sys
from argparse import ArgumentParser, Namespace
from .userconfig import (get_user_contexts,
                         get_current_user_context,
                         get_user_config_value,
                         load_user_config,
                         set_context,
                         save_userconfig
                         )

GLOBAL_DESC = __doc__


def warning(text: str) -> None:
    print(f"warning: {text}", file=sys.stderr, flush=True)


def notice(text: str) -> None:
    print(f"notice: {text}", file=sys.stderr, flush=True)


def print_contexts(data: dict):
    context_list = get_user_contexts(data)
    current = get_current_user_context(data)
    for item in context_list:
        mark = " "
        if item == current:
            mark = "*"
        print(f"{mark} {item}")


def set_context_cmd(opts: Namespace):
    data = load_user_config(force_reload=True)
    if opts.NAME is None:
        print_contexts(data)
    else:
        name = set_context(data, opts.NAME)
        notice(f"gle context set to {name}")
        save_userconfig(data)


def sensitive_varname(name) -> bool:
    for check in ["PASSWORD", "TOKEN", "PRIVATE"]:
        if check in name:
            return True
    return False


def print_sensitive_vars(vars: dict) -> None:
    for name in sorted(vars.keys()):
        if sensitive_varname(name):
            print(f"{name}=************")
        else:
            print(f"{name}={vars[name]}")


def trim_quotes(text: str) -> str:
    """If the string is wrapped in quotes, strip them off"""
    if text:
        if text[0] in ["'", "\""]:
            if text[0] == text[-1]:
                text = text[1:-1]
    return text


def vars_cmd(opts: Namespace):
    data = load_user_config(force_reload=True)
    context = get_current_user_context(data)
    variables = get_user_config_value(data, "docker", name="variables", default={})
    if opts.VAR is None:
        print_sensitive_vars(variables)
    elif "=" in opts.VAR:
        name, value = opts.VAR.split("=", 1)
        if not value:
            # unset variable if set
            if name in variables:
                notice(f"Unsetting {name}")
                del variables[name]
            else:
                warning(f"{name} is not set. If you want an empty string, use {name}='\"\"'")
        else:
            notice(f"Setting {name}")
            variables[name] = trim_quotes(value)

        if "docker" not in data[context]:
            data[context]["docker"] = {}
        data[context]["docker"]["variables"] = variables
        save_userconfig(data)
    else:
        if opts.VAR in variables:
            print_sensitive_vars({opts.VAR: variables[opts.VAR]})
        else:
            print(f"{opts.VAR} is not set")





def main(args=None):
    parser = ArgumentParser(description=GLOBAL_DESC)
    subparsers = parser.add_subparsers()

    set_ctx = subparsers.add_parser("context", help="Show/select the current and available gle contexts")
    set_ctx.add_argument("NAME", type=str, help="Name of the context to use (or create)", nargs="?")
    set_ctx.set_defaults(func=set_context_cmd)

    set_var = subparsers.add_parser("vars", help="Show/set environment variables injected into jobs")
    set_var.add_argument("VAR", type=str, help="Set or unset an environment variable", nargs="?")
    set_var.set_defaults(func=vars_cmd)

    opts = parser.parse_args(args)
    if hasattr(opts, "func"):
        opts.func(opts)
    else:
        parser.print_usage()


if __name__ == "__main__":
    main()
