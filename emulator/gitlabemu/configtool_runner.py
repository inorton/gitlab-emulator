import sys
from argparse import Namespace

import yaml

from .helpers import note, die, truth_string, setenv_string
from .userconfig import get_user_config
from .userconfigdata import GleRunnerConfig, DockerExecutorConfig, RUNNER_SHELL_SHELLS, RUNNER_EXECUTOR_TYPES, \
    EXECUTOR_DOCKER, DEFAULT_DOCKER_CLI


def setup_cmd(subparsers):
    runner = subparsers.add_parser("runner", help="Manage docker and shell executor settings and job tag handling")
    runner.add_argument("action", metavar="ACTION", type=str, choices=["add", "rm", "edit", "ls"],
                        nargs="?",
                        default="ls",
                        help="one of: add, rm, edit, ls")
    runner.add_argument("name", nargs="?", type=str,
                        help="Runner name to add/remove/edit")
    runner.add_argument("--tags", type=str, default=None,
                        help="Set the runner tags")
    runner.add_argument("--executor", type=str, choices=RUNNER_EXECUTOR_TYPES, default="docker",
                        help="Runner type")
    runner.add_argument("--untagged", default=None, type=truth_string, metavar="BOOL",
                        help="Make the runner run untagged jobs")

    runner.add_argument("--set", dest="setenv", type=setenv_string, metavar="NAME=VALUE", default=None,
                        help="Set an environment variable")
    runner.add_argument("--unset", dest="unsetenv", type=str, metavar="NAME", default=None,
                        help="Remove an environment variable")

    docker_group = runner.add_argument_group("docker runners")
    shell_group = runner.add_argument_group("shell options")

    docker_group.add_argument("--privileged", default=None, type=truth_string, metavar="BOOL",
                              help="Set a docker executor to use --privileged or not")
    docker_group.add_argument("--add-volume", type=str, metavar="VOLUME",
                              help="Add a docker volume")
    docker_group.add_argument("--remove-volume", type=str, metavar="VOLUME",
                              help="Remove a docker volume")
    docker_group.add_argument("--docker-cli", type=str, metavar="TOOL", default=None,
                              help="Use an alternate docker cli program (eg podman, nerdctl etc)")

    shell_group.add_argument("--shell", default=None, type=str, choices=RUNNER_SHELL_SHELLS,
                             help="Set the shell executor shell")

    runner.set_defaults(func=runner_cmd)


def runner_cmd(opts: Namespace):
    cfg = get_user_config()
    note(f"using {cfg.filename}")
    ctx = cfg.contexts[cfg.current_context]

    if opts.action == "ls":
        print(f"{'name':<18} {'executor':<0} {' ':<7} {'tags':<32} {'untagged':<8}", file=sys.stderr)
        print("-" * 78, file=sys.stderr, flush=True)
        runners = ctx.runners + ctx.builtin_runners()
        for runner in runners:
            opt = ""
            if runner.executor == "docker":
                if runner.docker.privileged:
                    opt = "priv"
            taglist = list(runner.tags)
            tags = ','.join(taglist)
            untagged = " "
            if runner.run_untagged:
                untagged = "*"
            print(f"{runner.name:18} {runner.executor:8} {opt:7} {tags:32} {untagged:8}")
    elif opts.action in ["add", "edit"]:
        if opts.action == "add":
            runner = GleRunnerConfig()
            if not opts.name:
                die("missing required runner name")
            runner.name = opts.name
            runner.executor = opts.executor
            if not ctx.can_add_name(runner.name):
                if ctx.get_runner(runner.name) is not None:
                    die(f"A runner named {runner.name} already exists")
                die(f"Cannot add a new runner named {runner.name}")
            if runner.executor == "docker":
                runner.docker = DockerExecutorConfig()
        else:
            runner = ctx.get_runner(opts.name, builtins=True)
            if runner is None:
                die(f"No such runner {opts.name}")
        before = str(runner.to_dict())
        if opts.untagged is not None:
            runner.run_untagged = opts.untagged
        if opts.tags is not None:
            runner.tags = opts.tags.split(",")
        if runner.executor == "docker":
            if opts.privileged is not None:
                runner.docker.privileged = opts.privileged
            if opts.add_volume:
                runner.docker.add_volume(opts.add_volume)
            if opts.remove_volume:
                runner.docker.remove_volume(opts.remove_volume)
            if opts.docker_cli is not None:
                runner.docker.docker_cli = opts.docker_cli
        if opts.setenv is not None:
            set_envname, set_envval = opts.setenv
            runner.environment[set_envname] = set_envval
        if opts.unsetenv is not None:
            if opts.unsetenv in runner.environment:
                del runner.environment[opts.unsetenv]
        if opts.shell is not None:
            runner.shell = opts.shell
        if not runner.is_builtin:
            ctx.save_runner(runner)
        after = str(runner.to_dict())
        if after != before:
            if runner.is_builtin:
                # some things we can alter in the global settings
                if runner.executor == EXECUTOR_DOCKER:
                    ctx.docker.privileged = runner.docker.privileged
                    ctx.docker.volumes = runner.docker.volumes
                    ctx.docker.variables = runner.environment
                    ctx.docker.docker_cli = runner.docker.docker_cli
            note(f"saved runner {runner.name} :-")
        else:
            note(f"current settings for runner {runner.name} :-")
        print(yaml.safe_dump(runner.to_dict(), indent=4))
        cfg.save()
    elif opts.action == "rm":
        if ctx.get_runner(opts.name) is not None:
            ctx.runners = [x for x in ctx.runners if x.name != opts.name]
            cfg.save()
            note(f"removed runner {opts.name}")
