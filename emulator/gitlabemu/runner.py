import re
import sys
import os
import argparse
from . import configloader
from .helpers import DockerTool, has_docker, is_linux

CONFIG_DEFAULT = ".gitlab-ci.yml"

parser = argparse.ArgumentParser(prog="{} -m gitlabemu".format(os.path.basename(sys.executable)))
parser.add_argument("--list", "-l", dest="LIST", default=False,
                    action="store_true",
                    help="List runnable jobs")
parser.add_argument("--hidden", default=False, action="store_true",
                    help="Show hidden jobs in --list(those that start with '.')")
parser.add_argument("--full", "-r", dest="FULL", default=False,
                    action="store_true",
                    help="Run any jobs that are dependencies")
parser.add_argument("--config", "-c", dest="CONFIG", default=CONFIG_DEFAULT,
                    type=str,
                    help="Use an alternative gitlab yaml file")

parser.add_argument("--enter", "-i", dest="enter_shell", default=False, action="store_true",
                    help="Run an interactive shell but do not run the build"
                    )
parser.add_argument("--user", "-u", dest="shell_is_user", default=False, action="store_true",
                    help="Run the interactive shell as the current user instead of root")

parser.add_argument("--shell-on-error", "-e", dest="error_shell", type=str,
                    help="If a docker job fails, execute this process (can be a shell)")

parser.add_argument("--ignore-docker", dest="no_docker", action="store_true", default=False,
                    help="If set, run jobs using the local system as a shell job instead of docker"
                    )

parser.add_argument("--var", dest="var", type=str, default=[], action="append",
                    help="Set a pipeline variable, eg DEBUG or DEBUG=1")

parser.add_argument("--revar", dest="revars", metavar="REGEX", type=str, default=[], action="append",
                    help="Set pipeline variables that match the given regex")

parser.add_argument("JOB", type=str, default=None,
                    nargs="?",
                    help="Run this named job")


def execute_job(config, jobname, seen=set(), recurse=False):
    """
    Run a job, optionally run required dependencies
    :param config: the config dictionary
    :param jobname: the job to start
    :param seen: completed jobs are added to this set
    :param recurse: if True, execute in dependency order
    :return:
    """
    if jobname not in seen:
        jobobj = configloader.load_job(config, jobname)
        if recurse:
            for need in jobobj.dependencies:
                execute_job(config, need, seen=seen, recurse=True)
        jobobj.run()
        seen.add(jobname)


def run(args=None):
    options = parser.parse_args(args)
    loader = configloader.Loader()
    yamlfile = options.CONFIG
    jobname = options.JOB
    try:
        fullpath = os.path.abspath(yamlfile)
        rootdir = os.path.dirname(fullpath)
        os.chdir(rootdir)
        loader.load(fullpath)
    except configloader.ConfigLoaderError as err:
        print("Config error: " + str(err))
        sys.exit()

    hide_dot_jobs = not options.hidden

    if options.LIST:
        for jobname in sorted(loader.get_jobs()):
            if jobname.startswith(".") and hide_dot_jobs:
                continue
            print(jobname)
    elif not jobname:
        parser.print_usage()
        sys.exit(1)
    else:
        jobs = sorted(loader.get_jobs())
        if jobname not in jobs:
            print(f"No such job {jobname}")
            sys.exit(1)

        fix_ownership = has_docker()
        if options.no_docker:
            loader.config["hide_docker"] = True
            fix_ownership = False

        if not loader.get_docker_image(jobname):
            fix_ownership = False

        if not is_linux():
            fix_ownership = False

        for item in options.revars:
            patt = re.compile(item)
            for name in os.environ:
                if patt.search(name):
                    loader.config["variables"][name] = os.environ.get(name)

        for item in options.var:
            var = item.split("=", 1)
            if len(var) == 2:
                name, value = var[0], var[1]
            else:
                name = var[0]
                value = os.environ.get(name, None)

            if value is not None:
                loader.config["variables"][name] = value

        if options.enter_shell:
            if options.FULL:
                print("-i is not compatible with --full")
                sys.exit(1)
        loader.config["enter_shell"] = options.enter_shell
        loader.config["shell_is_user"] = options.shell_is_user

        if options.error_shell:
            loader.config["error_shell"] = [options.error_shell]
        try:
            execute_job(loader.config, jobname, recurse=options.FULL)
        finally:
            if has_docker() and fix_ownership:
                if is_linux():
                    print("Fixing up local file ownerships..")
                    dt = DockerTool()
                    dt.image = "alpine:latest"
                    dt.entrypoint = ["/bin/sh"]
                    dt.name = "gitlab-emulator-chowner-{}".format(os.getpid())
                    folder = os.getcwd()
                    current_user = os.getuid()
                    current_grp = os.getgid()
                    dt.add_volume(folder, folder)
                    dt.run()
                    try:
                        dt.check_call(folder,
                                      ["chown", "-R", f"{current_user}.{current_grp}", "."])
                    finally:
                        dt.kill()
                    print("finished")
        print("Build complete!")
