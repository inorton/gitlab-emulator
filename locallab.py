#!/usr/bin/env python
"""
Run a job from a .gitlab-ci.yml file
"""

import os
import argparse
from gitlabemu import configloader

CONFIG_DEFAULT = ".gitlab-ci.yml"

parser = argparse.ArgumentParser()
parser.add_argument("--list", dest="LIST", default=False,
                    action="store_true",
                    help="List runnable jobs")
parser.add_argument("--full", dest="FULL", default=False,
                    action="store_true",
                    help="Run any jobs that are dependencies")
parser.add_argument("--config", dest="CONFIG", default=CONFIG_DEFAULT,
                    type=str,
                    help="Use an alternative gitlab yaml file")
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


def run():
    options = parser.parse_args()

    yamlfile = options.CONFIG
    jobname = options.JOB
    config = configloader.read(yamlfile)

    if options.LIST:
        for jobname in sorted(configloader.get_jobs(config)):
            print(jobname)
    else:
        execute_job(config, jobname, recurse=options.FULL)


if __name__ == "__main__":
    run()
