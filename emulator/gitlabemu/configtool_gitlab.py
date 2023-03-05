from argparse import Namespace

from .helpers import die
from .userconfig import get_user_config


def setup_cmd(subparsers):
    gl_ctx = subparsers.add_parser("gitlab", help="Update remote gitlab configurations")
    gl_ctx.add_argument("NAME", type=str, help="Set the name", default=None, nargs="?")
    gl_ctx.add_argument("--server", type=str, help="Set the URL for a gitlab server",
                        default=None)
    gl_ctx.add_argument("--insecure", default=True, action="store_false", dest="tls_verify",
                        help="Disable TLS certificate verification for this server (default is to verify)")
    gl_ctx.add_argument("--token", type=str,
                        help="Set the gitlab API token (should have git and api write access for best use)")
    gl_ctx.set_defaults(func=gitlab_cmd)


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
