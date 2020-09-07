"""
Various useful common funcs
"""
import os
import sys
import platform
import subprocess


class DockerTool(object):
    """
    Control docker containers
    """
    def __init__(self):
        self.container = None
        self.image = None
        self.env = {}
        self.volumes = []
        self.name = None
        self.privileged = False
        self.entrypoint = None
        self.pulled = None
        self.network = None

    def add_volume(self, outside, inside):
        self.volumes.append("{}:{}".format(outside, inside))

    def add_env(self, name, value):
        self.env[name] = value

    def pull(self):
        self.pulled = subprocess.Popen(["docker", "pull", self.image],
                                       stdin=None,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
        return self.pulled

    def get_envs(self):
        cmdline = []
        for name in self.env:
            value = self.env.get(name)
            if value is not None:
                cmdline.extend(["-e", "{}={}".format(name, value)])
            else:
                cmdline.extend(["-e", name])
        return cmdline

    def wait(self):
        cmdline = ["docker", "container", "wait", self.container]
        subprocess.check_call(cmdline)

    def run(self):
        cmdline = ["docker", "run", "--rm",
                   "--name", self.name,
                   "-d"]
        if platform.system() != "Windows":
            if self.privileged:
                cmdline.append("--privileged")
        if self.network:
            cmdline.extend(["--network", self.network])

        cmdline.extend(self.get_envs())

        for volume in self.volumes:
            cmdline.extend(["-v", "{}:rw".format(volume)])

        if self.entrypoint is not None:
            # docker run does not support multiple args for entrypoint
            if self.entrypoint == ["/bin/sh", "-c"]:
                self.entrypoint = [""]
            if self.entrypoint == [""]:
                self.entrypoint = ["/bin/sh"]

            if len(self.entrypoint) > 1:
                raise RuntimeError("gitlab-emulator cannot yet support "
                                   "multiple args for docker entrypoint "
                                   "overrides")

            cmdline.extend(["--entrypoint", " ".join(self.entrypoint)])

        cmdline.extend(["-i", self.image])

        self.container = subprocess.check_output(cmdline, shell=False).decode().strip()

    def kill(self):
        cmdline = ["docker", "kill", self.container]
        subprocess.check_output(
            cmdline, shell=False)

    def check_call(self, cwd, cmd):
        cmdline = ["docker", "exec", "-w", cwd, self.container] + cmd
        subprocess.check_call(cmdline)

    def exec(self, cwd, shell):
        cmdline = ["docker", "exec", "-w", cwd]
        cmdline.extend(self.get_envs())
        cmdline.extend(["-i", self.container])
        cmdline.extend(shell)
        proc = subprocess.Popen(cmdline,
                                cwd=cwd,
                                shell=False,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        return proc


def communicate(process, stdout=sys.stdout, script=None, throw=False, linehandler=None):
    """
    Write output incrementally to stdout
    :param process: a POpen child process
    :type Popen
    :param stdout: a file-like object to write to
    :param script: a script (ie, bytes) to stream to stdin
    :param throw: raise an exception if the process exits non-zero
    :param linehandler: if set, pass the line to this callable
    :return:
    """
    if script is not None:
        process.stdin.write(script)
        process.stdin.flush()
        process.stdin.close()

    while process.poll() is None:
        try:
            data = process.stdout.readline()
            if data and linehandler:
                linehandler(data)

        except ValueError:
            pass

        if data:
            stdout.write(data.decode())

    # child has exited now, get any last output if there is any
    if not process.stdout.closed:
        stdout.write(process.stdout.read().decode())

    if hasattr(stdout, "flush"):
        stdout.flush()

    if throw:
        if process.returncode != 0:
            args = []
            if hasattr(process, "args"):
                args = process.args
            raise subprocess.CalledProcessError(process.returncode, cmd=args)


def has_docker():
    try:
        subprocess.check_output(["docker", "ps"], stderr=subprocess.STDOUT)
        return True
    except Exception as err:
        return err is None


def is_windows():
    return platform.system() == "Windows"

