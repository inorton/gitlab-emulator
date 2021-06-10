#!/usr/bin/python
"""
A Pure Python gitlab runner
"""

import argparse

import os
import sys

import time
import yaml
from requests.exceptions import ConnectionError, HTTPError
from . import consts, runner, executor, common, service
from gitlabemu import logmsg


parser = argparse.ArgumentParser(prog="{} -m GitlabPyRunner".format(sys.executable))
parser.add_argument("--register",
                    type=str,
                    help="Register a new runner with the server",
                    )
parser.add_argument("--regtoken",
                    type=str,
                    default=None,
                    help="Registration token for --register")
parser.add_argument("--unregister",
                    default=False, action="store_true",
                    help="De-register the runner")

parser.add_argument("--type", type=str,
                    default="shell",
                    help="Set the runner executor eg(shell, docker)")

parser.add_argument("--shell", type=str,
                    help="Set the executor shell")

parser.add_argument("--desc", type=str,
                    help="Set the runner description")

parser.add_argument("--tag", type=str, action="append",
                    help="Add a tag when registering a runner",
                    )
parser.add_argument("--start", type=str,
                    help="Start the runner defined in the config file"
                    )

parser.add_argument("--trace-http", default=False, action="store_true", dest="httpdebug",
                    help="Log HTTP requests and responses for debugging purposes only"
                    )

parser.add_argument("--once", action="store_true", default=False,
                    help="Run only one job and then exit"
                    )

installer = service.get_installer()

if installer is not None:
    parser.add_argument("--install", type=str, default=None, metavar="CONFIG", dest="install",
                        help="Launch gitlab-runner.py on boot using the given CONFIG file")

    parser.add_argument("--user", type=str, default=None,
                        help="User to use for --install")

    parser.add_argument("--uninstall", action="store_true", default=False, dest="uninstall",
                        help="Remove boot-time startup scripts (undo --install)")


def run():
    opts = parser.parse_args()

    if installer:
        if opts.uninstall:
            installer.uninstall()
            return
        if opts.install:
            installer.install(opts.install, opts.user)
            return

    if opts.register:
        if not opts.desc:
            opts.desc = consts.NAME + " on " + common.gethostname()

        if not opts.tag:
            opts.tag = ["new-python-runner-" + common.gethostname()]

        if not opts.regtoken:
            raise RuntimeError("missing required --regtoken")

        if not opts.shell:
            opts.shell = os.getenv("COMSPEC", "/bin/sh")

        instance = runner.Runner(opts.register, None)
        if opts.shell:
            os.environ["SHELL"] = opts.shell  # TODO pass this into GLE better
        instance.register(opts.desc, opts.regtoken, opts.tag)

        if not instance.token:
            raise RuntimeError("runner register failed")

        # save the runner config
        tosave = {
            "server": opts.register,
            "token": instance.token,
            "executor": opts.type,
            "shell": opts.shell,
            "dir": os.getcwd(),
        }
        if opts.type == "docker":
            tosave["volumes"] = []

        common.save_config("gitlab-runner.yml", tosave)

        logmsg.info("Registration complete. Config saved at '{}'".format(os.path.join(os.getcwd(),
                                                                                      "gitlab-runner.yml")))
        sys.exit(0)

    if opts.unregister:
        config = common.parse_config("gitlab-runner.yml")
        logmsg.info("De-registering..")
        instance = runner.Runner(config["server"], config["token"])
        instance.unregister()
        logmsg.info("De-register complete")
        sys.exit(0)

    if opts.start:
        if opts.httpdebug:
            common.set_trace_http_requests(True)

        config = common.parse_config(opts.start)
        os.chdir(config["dir"])
        extype = config["executor"]
        if extype == "docker":
            os.environ["GLE_DOCKER_VOLUMES"] = ""
            volumes = config.get("volumes", None)
            if volumes:
                os.environ["GLE_DOCKER_VOLUMES"] = ",".join(volumes)

        if opts.once:
            logmsg.info("Will exit after one job")

        exitstatus = 1

        docker = False

        # loop forever to cope with some common errors that can come up
        while True:
            if extype == "shell":
                instance = runner.Runner(config["server"], config["token"])
            elif extype == "docker":
                docker = True
                instance = runner.DockerRunner(config["server"], config["token"])
            else:
                raise RuntimeError("unsupported executor type '{}'".format(extype))

            try:
                instance.shell = config["shell"]
                while True:
                    exitstatus = 1
                    result = None
                    interval = 40
                    logmsg.info("Polling for jobs.. ({} sec)".format(interval))
                    job = instance.poll()
                    if not job:
                        time.sleep(interval)
                    else:
                        logmsg.info("Got new job.")
                        try:
                            result = executor.run(instance, job, docker)
                            if result:
                                exitstatus = 0
                        except Exception as rerr:
                            logmsg.warning("Executor had exception {}".format(rerr))

                        finally:
                            logmsg.info("Job {} has ended success={}".format(job["id"], result))
                            if result:
                                instance.success(job)
                            else:
                                if result is None:
                                    logmsg.warning("Job {} failed early setup, see job logs".format(job["id"]))
                                instance.failed(job)
                            if opts.once:
                                break

            except (ConnectionError, HTTPError) as err:
                aborted = False
                if not result:
                    if job:
                        if err.response.status_code == 403:
                            # job was aborted by the server
                            aborted = True
                if aborted:
                    logmsg.info("Job {} was cancelled".format(job["id"]))
                else:
                    logmsg.warning("comms exception {}".format(err))
                    logmsg.warning("sleeping..")
                    time.sleep(10)
            finally:
                if opts.once:
                    break

        sys.exit(exitstatus)
