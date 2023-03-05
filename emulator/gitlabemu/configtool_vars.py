from argparse import Namespace

from .helpers import trim_quotes, sensitive_varname, warning, notice
from .userconfig import get_user_config

def setup_cmd(subparsers):
    set_var = subparsers.add_parser("vars", help="Show/set environment variables injected into jobs")
    set_var.add_argument("--local", default=False, action="store_true",
                         help="Set/Show variables for local shell jobs only")
    set_var.add_argument("--docker", default=False, action="store_true",
                         help="Set/Show variables for local docker jobs only")
    set_var.add_argument("VAR", type=str, help="Set or unset an environment variable", nargs="?")
    set_var.set_defaults(func=vars_cmd)

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


def print_sensitive_vars(variables: dict) -> None:
    for name in sorted(variables.keys()):
        if sensitive_varname(name):
            print(f"{name}=************")
        else:
            print(f"{name}={variables[name]}")
