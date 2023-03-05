from argparse import Namespace, ArgumentParser

from .helpers import notice
from .userconfig import get_user_config
from .userconfigdata import DEFAULT_CONTEXT, UserContext


def setup_cmd(subparsers):
    set_ctx = subparsers.add_parser("context", help="Show/select the current and available gle contexts")
    set_ctx.add_argument("NAME", type=str, help="Name of the context to use (or create)", nargs="?")
    set_ctx.add_argument("--remove", default=False, action="store_true",
                         help="Remove the context")
    set_ctx.set_defaults(func=set_context_cmd)


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


def print_contexts():
    cfg = get_user_config()
    current = cfg.current_context
    for item in cfg.contexts:
        mark = " "
        if item == current:
            mark = "*"
        print(f"{mark} {item}")
