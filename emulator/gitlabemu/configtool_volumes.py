from argparse import Namespace

from .userconfig import get_user_config


def setup_cmd(subparsers):
    set_vols = subparsers.add_parser("volumes", help="Show/set the global docker volumes")
    vol_grp = set_vols.add_mutually_exclusive_group()
    vol_grp.add_argument("--add", type=str, metavar="VOLUME",
                         help="Volume to add (eg /path/to/folder:/mount/path:rw)")
    vol_grp.add_argument("--remove", type=str, metavar="PATH",
                         help="Volume to remove (eg /mount/path)")
    set_vols.set_defaults(func=volumes_cmd)


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
