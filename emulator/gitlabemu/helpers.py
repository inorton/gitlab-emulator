"""
Various useful common funcs
"""
from threading import Thread
import json
import sys
import re
import platform
import subprocess

from .errors import DockerExecError


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

    def inspect(self):
        """
        Inspect the image and return the Config dict
        :return:
        """
        cmdline = ["docker", "inspect", self.image]
        stdout = subprocess.check_output(cmdline, shell=False).decode()
        data = json.loads(stdout)
        if data and len(data) == 1:
            datadict = data[0]
            return datadict.get("Config", {})
        return {}

    def get_user(self):
        return self.inspect().get("User", None)

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

        for volume in self.volumes:
            entry = volume
            if not entry.endswith(":ro") and not entry.endswith(":rw"):
                entry += ":rw"
            cmdline.extend(["-v", entry])

        if self.entrypoint is not None:
            # docker run does not support multiple args for entrypoint
            if self.entrypoint == ["/bin/sh", "-c"]:
                self.entrypoint = [""]
            if self.entrypoint == [""]:
                self.entrypoint = ["/bin/sh"]

            cmdline.extend(["--entrypoint", " ".join(self.entrypoint)])

        cmdline.append("-i")
        cmdline.extend(self.get_envs())
        cmdline.append(self.image)
        self.container = subprocess.check_output(cmdline, shell=False).decode().strip()

    def kill(self):
        cmdline = ["docker", "kill", self.container]
        subprocess.check_output(
            cmdline, shell=False)

    def check_call(self, cwd, cmd):
        cmdline = ["docker", "exec", "-w", cwd, self.container] + cmd
        subprocess.check_call(cmdline)

    def exec(self, cwd, shell, tty=False, user=None):
        cmdline = ["docker", "exec", "-w", cwd]
        cmdline.extend(self.get_envs())
        if user is not None:
            cmdline.extend(["-u", str(user)])
        if tty:
            cmdline.append("-t")

        cmdline.extend(["-i", self.container])
        cmdline.extend(shell)

        if not tty:
            proc = subprocess.Popen(cmdline,
                                    cwd=cwd,
                                    shell=False,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            return proc
        else:
            return subprocess.call(cmdline, cwd=cwd, shell=False)


class ProcessLineProxyThread(Thread):
    def __init__(self, process, stdout, linehandler=None):
        super(ProcessLineProxyThread, self).__init__()
        self.errors = []
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
            if self.linehandler:
                try:
                    self.linehandler(data)
                except DockerExecError as err:
                    self.errors.append(err)

    def run(self):
        while True:
            try:
                data = self.process.stdout.readline()
            except ValueError:
                pass
            except Exception as err:
                self.errors.append(err)
                raise
            finally:
                if data:
                    self.writeout(data)
            if self.process.poll() is not None:
                break

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

    # use a thread to stream build output if we can (hpux can't)
    if comm_thread and thread_started:
        while process.poll() is None:
            if comm_thread.is_alive():
                comm_thread.join(timeout=5)

        if comm_thread.is_alive():
            comm_thread.join()

    # either the task has ended or we could not create a thread, either way,
    # stream the remaining stdout data
    while True:
        try:
            data = process.stdout.readline()
        except ValueError:
            pass
        if data:
            # we can still use our proxy object to decode and write the data
            comm_thread.writeout(data)

        if process.poll() is not None:
            break

    # process has definitely already ended, read all the lines, this wont deadlock
    while True:
        line = process.stdout.readline()
        if line:
            comm_thread.writeout(line)
        else:
            break

    if throw:
        if process.returncode != 0:
            args = []
            if hasattr(process, "args"):
                args = process.args
            raise subprocess.CalledProcessError(process.returncode, cmd=args)

    if comm_thread:
        for err in comm_thread.errors:
            if isinstance(err, DockerExecError) or throw:
                raise err


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
