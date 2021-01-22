"""
Various useful common funcs
"""
from threading import Thread

import sys
import re
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


class ProcessLineProxyThread(Thread):
    def __init__(self, process, stdout, linehandler=None):
        super(ProcessLineProxyThread, self).__init__()
        self.process = process
        self.stdout = stdout
        self.linehandler = linehandler
        self.daemon = True

    def writeout(self, data):
        if self.stdout and data:
            try:
                decoded = data.decode()
            except UnicodeDecodeError:
                decoded = str(data)
            self.stdout.write(decoded)

    def run(self):
        while self.process.poll() is None:
            try:
                data = self.process.stdout.readline()
                if data and self.linehandler:
                    self.linehandler(data)
            except ValueError:
                pass
            self.writeout(data)

        # child has exited now, get any last output if there is any
        if not self.process.stdout.closed:
            self.writeout(self.process.stdout.read())

        if hasattr(self.stdout, "flush"):
            self.stdout.flush()


def communicate(process, stdout=sys.stdout, script=None, throw=False, linehandler=None):
    """
    Write output incrementally to stdout, waits for process to end
    :param process: a Popened child process
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

    comm_thread = ProcessLineProxyThread(process, stdout, linehandler=linehandler)
    thread_started = False
    try:
        comm_thread.start()
        thread_started = True
    except RuntimeError:
        # could not create the thread, so use a loop
        pass

    if comm_thread and thread_started:
        while comm_thread.is_alive() and process.poll() is None:
            comm_thread.join(timeout=5)
            # yes, if the process is dead we potentially leak a sleeping thread
            # blocked by readline..
    else:
        # could not create a thread (hpux?)
        while process.poll() is None:
            try:
                data = process.stdout.readline()
                if data and linehandler:
                    linehandler(data)

            except ValueError:
                pass

            if data:
                # we can still use our proxy object to decode and write the data
                comm_thread.writeout(data)

    if throw:
        if process.returncode != 0:
            args = []
            if hasattr(process, "args"):
                args = process.args
            raise subprocess.CalledProcessError(process.returncode, cmd=args)


def has_docker():
    try:
        subprocess.check_output(["docker", "info"], stderr=subprocess.STDOUT)
        return True
    except Exception as err:
        return err is None


def is_windows():
    return platform.system() == "Windows"


def is_linux():
    return platform.system() == "Linux"


def parse_timeout(text):
    """
    Decode a human readable time to seconds.
    eg, 1h 30m

    default is minutes without any suffix
    """
    # collapse the long form
    text = text.replace(" hours", "h")
    text = text.replace(" minutes", "m")

    words = text.split()
    seconds = 0

    if len(words) == 1:
        # plain single time
        word = words[0]
        try:
            mins = float(word)
            # plain bare number, use it as minutes
            return int(60.0 * mins)
        except ValueError:
            pass

    pattern = re.compile(r"([\d\.]+)\s*([hm])")

    for word in words:
        m = pattern.search(word)
        if m and m.groups():
            num, suffix = m.groups()
            num = float(num)
            if suffix == "h":
                if seconds > 0:
                    raise ValueError("Unexpected h value {}".format(text))
                seconds += num * 60 * 60
            elif suffix == "m":
                seconds += num * 60

    if seconds == 0:
        raise ValueError("Cannot decode timeout {}".format(text))
    return seconds
