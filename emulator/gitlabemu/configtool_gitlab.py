from argparse import Namespace, ArgumentParser
from pathlib import Path
from typing import Optional

from .helpers import die
from .userconfig import get_user_config


def setup_cmd(subparsers):
    gl_ctx: ArgumentParser = subparsers.add_parser("gitlab", help="Update remote gitlab configurations")
    gl_ctx.add_argument("NAME", type=str, help="Set the name", default=None, nargs="?")
    gl_ctx.add_argument("--server", type=str, help="Set the URL for a gitlab server",
                        default=None)
    tls = gl_ctx.add_mutually_exclusive_group()
    tls.add_argument("--insecure", default=True, action="store_false", dest="tls_verify",
                     help="Disable TLS certificate verification for this server (default is to verify)")
    tls.add_argument("--ca-cert", type=Path, dest="tls_ca_cert",
                     help="Add a CA cert for this gitlab server")
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
        ca_cert: Optional[Path] = opts.tls_ca_cert
        if ca_cert:
            if not ca_cert.is_file():
                die(f"CA cert {ca_cert} not found")
            ca_cert = ca_cert.absolute()

        matched = [x for x in ctx.gitlab.servers if x.name == opts.NAME]
        if len(matched):
            first = matched[0]
            if opts.token:
                first.token = opts.token
            first.tls_verify = opts.tls_verify
            if ca_cert:
                first.ca_cert = str(ca_cert)
        else:
            # add a new one
            if opts.server and opts.token:
                ctx.gitlab.add(opts.NAME, opts.server, opts.token, opts.tls_verify, ca_cert)
            else:
                die("Adding a new gitlab server entry requires --server URL and --token TOKEN")
        cfg.save()
