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
parser.add_argument("--full", "-r", dest="FULL", default=False,
                    action="store_true",
                    help="Run any jobs that are dependencies")
parser.add_argument("--config", "-c", dest="CONFIG", default=CONFIG_DEFAULT,
                    type=str,
                    help="Use an alternative gitlab yaml file")

parser.add_argument("--shell-on-error", "-e", dest="error_shell", type=str,
                    help="If a docker job fails, execute this process (can be a shell)")

parser.add_argument("--ignore-docker", dest="no_docker", action="store_true", default=False,
                    help="If set, run jobs using the local system as a shell job instead of docker"
                    )

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

    yamlfile = options.CONFIG
    jobname = options.JOB
    try:
        fullpath = os.path.abspath(yamlfile)
        rootdir = os.path.dirname(fullpath)
        os.chdir(rootdir)
        config = configloader.read(fullpath, topdir=rootdir)
    except configloader.ConfigLoaderError as err:
        print("Config error: " + str(err))
        sys.exit()

    if options.LIST:
        for jobname in sorted(configloader.get_jobs(config)):
            if not jobname.startswith("."):
                print(jobname)
    elif not jobname:
        parser.print_usage()
        sys.exit(1)
    else:
        fix_ownership = has_docker()
        if options.no_docker:
            config["hide_docker"] = True
            fix_ownership = False

        if not configloader.job_docker_image(config, jobname):
            fix_ownership = False

        if not is_linux():
            fix_ownership = False

        if options.error_shell:
            config["error_shell"] = [options.error_shell]
        try:
            execute_job(config, jobname, recurse=options.FULL)
        finally:
            if has_docker() and fix_ownership:
                if is_linux():
                    print("Fixing up local file ownerships..")
                    dt = DockerTool()
                    dt.image = "alpine:latest"
                    dt.entrypoint = ["/bin/sh"]
                    dt.name = "gitlab-emulator-chowner-{}".format(os.getpid())
                    dt.add_volume(os.getcwd(), os.getcwd())
                    dt.run()
                    try:
                        dt.check_call(os.getcwd(),
                                      ["chown", "-R", str(os.getuid()), str(os.getcwd())])
                    finally:
                        dt.kill()
                    print("finished")
        print("Build complete!")

