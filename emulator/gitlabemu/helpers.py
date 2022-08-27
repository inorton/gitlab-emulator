"""
Various useful common funcs
"""
import os.path
from threading import Thread
import sys
import re
import platform
import subprocess
from typing import Optional, List, Dict, Union

from .errors import DockerExecError
from .resnamer import resource_owner_alive, is_gle_resource
from .logmsg import info


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
            encoding = "ascii"
            if hasattr(self.stdout, "encoding"):
                encoding = self.stdout.encoding
            try:
                decoded = data.decode(encoding, "namereplace")
                self.stdout.write(decoded)
            except (TypeError, UnicodeError):
                # codec cant handle namereplace or the codec cant represent this.
                # decode it to utf-8 and replace non-printable ascii with
                # chars with '?'
                decoded = data.decode("utf-8", "replace")
                text = re.sub(r'[^\x00-\x7F]', "?", decoded)
                self.stdout.write(text)

            if self.linehandler:
                try:
                    self.linehandler(data)
                except DockerExecError as err:
                    self.errors.append(err)

    def run(self):
        while True:
            try:
                data = self.process.stdout.readline()
            except ValueError:  # pragma: no cover
                pass
            except Exception as err:  # pragma: no cover
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
    except RuntimeError:  # pragma: no cover
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
        except ValueError:  # pragma: no cover
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


def is_windows():
    return platform.system() == "Windows"


def is_linux():
    return platform.system() == "Linux"


def is_apple():
    return platform.system() == "Darwin"


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


def git_worktree(path: str) -> Optional[str]:
    """
    If the given path contains a git worktree, return the path to it
    :param path:
    :return:
    """
    gitpath = os.path.join(path, ".git")

    if os.path.isfile(gitpath):  # pragma: no cover
        # this is an odd case where you have .git files instead of folders
        with open(gitpath, "r") as fd:
            full = fd.read()
            for line in full.splitlines():
                name, value = line.split(":", 1)
                if name == "gitdir":
                    value = value.strip()
                    realpath = value
                    # keep going upwards until we find a .git folder
                    for _ in value.split(os.sep):
                        realpath = os.path.dirname(realpath)
                        gitdir = os.path.join(realpath, ".git")
                        if os.path.isdir(gitdir):
                            return gitdir
    return None


def make_path_slug(text: str) -> str:
    """Convert a string into one suitable for a folder basename"""
    return re.sub(r"[^a-zA-Z0-9\-\.]", "_", text)


def debug_enabled():
    return os.environ.get("GITLAB_EMULATOR_DEBUG", "no") in ["1", "y", "yes"]


def debug_print(msg):
    if debug_enabled():  # pragma: no cover
        print("GLE DEBUG: {}".format(msg))


def clean_leftovers():
    """Clean up any unused leftover docker containers or networks"""
    from .dockersupport import docker
    if docker:
        from .docker import DockerTool
        tool = DockerTool()
        for container in tool.client.containers.list():
            name = container.name
            pid = is_gle_resource(name)
            if pid is not None:
                if not resource_owner_alive(name):
                    # kill this container
                    info(f"Killing leftover docker container: {name}")
                    container.kill()

        for network in tool.client.networks.list():
            pid = is_gle_resource(network.name)
            if pid is not None:
                if not resource_owner_alive(network.name):
                    info(f"Remove leftover docker network: {network.name}")
                    network.remove()


class DockerVolume:
    def __init__(self, host, mount, mode):
        if host != "/":
            host = host.rstrip(os.sep)
        self.host = host
        self.mount = mount.rstrip(os.sep)
        assert mode in ["rw", "ro"]
        self.mode = mode

    def __str__(self):
        return f"{self.host}:{self.mount}:{self.mode}"


def plausible_docker_volume(text: str) -> Optional[DockerVolume]:
    """Decode a docker volume string or return None"""
    mode = "rw"
    parts = text.split(":")
    src = None
    mount = None
    if len(parts) >= 4:
        import ntpath
        # c:\thing:c:\container
        # c:\thing:c:\container[:mode]
        if len(parts) == 5:
            # has mode
            mode = parts[-1]
        src = ntpath.abspath(f"{parts[0]}:{parts[1]}")
        mount = ntpath.abspath(f"{parts[2]}:{parts[3]}")
    else:
        if len(parts) >= 2:
            import posixpath
            # /host/path:/mount/path[:mode]
            src = posixpath.abspath(parts[0])
            mount = posixpath.abspath(parts[1])
            if len(parts) == 3:
                mode = parts[2]
    if not src:
        return None
    return DockerVolume(src, mount, mode)


def sensitive_varname(name) -> bool:
    """Return True if the variable might be a sensitive/secret one"""
    for check in ["PASSWORD", "TOKEN", "PRIVATE"]:
        if check in name:
            return True
    return False


def trim_quotes(text: str) -> str:
    """If the string is wrapped in quotes, strip them off"""
    if text:
        if text[0] in ["'", "\""]:
            if text[0] == text[-1]:
                text = text[1:-1]
    return text


def powershell_escape(text: str, variables=False) -> str:
    # pragma: linux no cover
    # taken from: http://www.robvanderwoude.com/escapechars.php
    text = text.replace("`", "``")
    text = text.replace("\a", "`a")
    text = text.replace("\b", "`b")
    text = text.replace("\f", "^f")
    text = text.replace("\r", "`r")
    text = text.replace("\n", "`n")
    text = text.replace("\t", "^t")
    text = text.replace("\v", "^v")
    text = text.replace("#", "`#")
    text = text.replace("'", "`'")
    text = text.replace("\"", "`\"")
    text = f"\"{text}\""
    if variables:
        text = text.replace("$", "`$")
        text = text.replace("``e", "`e")
    return text


def die(msg):
    """print an error and exit"""
    print("error: " + str(msg), file=sys.stderr)
    sys.exit(1)


def note(msg):
    """Print to stderr"""
    print(msg, file=sys.stderr, flush=True)


def git_uncommitted_changes(path: str) -> bool:
    """Return True if the given repo has uncommitted changes to tracked files"""
    topdir = git_top_level(path)
    output = subprocess.check_output(
        ["git", "-C", topdir, "status", "--porcelain", "--untracked=no"],
        encoding="utf-8", stderr=subprocess.DEVNULL).strip()
    for _ in output.splitlines(keepends=False):
        return True
    return False


def git_current_branch(path: str) -> str:
    """Get the current branch"""
    return subprocess.check_output(
        ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"], encoding="utf-8", stderr=subprocess.DEVNULL
    ).strip()


def git_commit_sha(path: str) -> str:
    """Get the current commit hash"""
    return subprocess.check_output(
        ["git", "-C", path, "rev-parse", "HEAD"], encoding="utf-8", stderr=subprocess.DEVNULL
    ).strip()


def git_remotes(path: str) -> List[str]:
    """Get the remote names of the given git repo"""
    try:
        output = subprocess.check_output(
            ["git", "-C", path, "remote"], encoding="utf-8", stderr=subprocess.DEVNULL)
        return list(output.splitlines(keepends=False))
    except subprocess.CalledProcessError:
        return []


def git_remote_url(path: str, remote: str) -> str:
    """Get the URL of the given git remote"""
    return subprocess.check_output(
        ["git", "-C", path, "remote", "get-url", remote], encoding="utf-8", stderr=subprocess.DEVNULL).strip()


def get_git_remote_urls(repo: str) -> Dict[str, str]:
    """Return all the git remotes defined in the given git repo"""
    remotes = git_remotes(repo)
    urls = {}
    for item in remotes:
        urls[item] = git_remote_url(repo, item)
    return urls


def git_top_level(repo: str) -> str:
    """Get the top folder of the git repo"""
    return subprocess.check_output(
        ["git", "-C", repo, "rev-parse", "--show-toplevel"], encoding="utf-8", stderr=subprocess.DEVNULL).strip()


def git_push_force_upstream(repo: str, remote: str, branch: str):  # pragma: no cover
    subprocess.check_call(["git", "-C", repo, "push", "--force", "-q", "--set-upstream", remote, branch])


def stringlist_if_string(value: Union[str, list]) -> list:
    """If value is a string, return a one element list, else return value"""
    if isinstance(value, str):
        return [value]
    return value
