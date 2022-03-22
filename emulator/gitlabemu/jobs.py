"""
Represent a gitlab job
"""
import os
import signal

import sys
import platform
import subprocess
import tempfile
import threading
import time
from .logmsg import info, fatal
from .errors import GitlabEmulatorError
from .helpers import communicate as comm, is_windows
from .helpers import parse_timeout


class NoSuchJob(GitlabEmulatorError):
    """
    Could not find a job with the given name
    """
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "NoSuchJob {}".format(self.name)


class Job(object):
    """
    A Gitlab Job
    """
    def __init__(self):
        self.name = None
        self.build_process = None
        self.before_script = []
        self.script = []
        self.after_script = []
        self.error_shell = []
        self.enter_shell = False
        self.before_script_enter_shell = False
        self.shell_is_user = False
        self.tags = []
        self.stage = "test"
        self.variables = {}
        self.dependencies = []
        if platform.system() == "Windows":
            self.shell = ["powershell.exe",
                          "-NoProfile",
                          "-NonInteractive",
                          "-ExecutionPolicy",
                          "Bypass"]
        else:
            self.shell = ["/bin/sh"]
        self.workspace = None
        self.stderr = sys.stderr
        self.stdout = sys.stdout
        self.started_time = 0
        self.ended_time = 0
        self.timeout_seconds = 0
        self.monitor_thread = None
        self.exit_monitor = False

    def interactive_mode(self):
        """Return True if in interactive mode"""
        return self.enter_shell or self.before_script_enter_shell

    def __str__(self):
        return "job {}".format(self.name)

    def duration(self):
        if self.started_time:
            return time.time() - self.started_time
        return 0

    def monitor_thread_loop_once(self):
        """
        Execute each time around the monitor loop
        """
        # check for timeout
        if self.timeout_seconds:
            duration = self.duration()
            if duration > self.timeout_seconds:
                info(f"Job exceeded {int(self.timeout_seconds)} sec timeout")
                self.abort()
                self.exit_monitor = True

    def monitor_thread_loop(self):
        """
        Executed by the monitor thread when a job is started
        and exits when it finishes
        """
        while not self.exit_monitor:
            self.monitor_thread_loop_once()
            time.sleep(2)

    def is_powershell(self) -> bool:
        return "powershell.exe" in self.shell

    def load(self, name, config):
        """
        Load a job from a dictionary
        :param name:
        :param config:
        :return:
        """
        self.workspace = config[".gitlab-emulator-workspace"]
        self.name = name
        job = config[name]
        self.shell = config.get(".gitlabemu-windows-shell", self.shell)
        self.error_shell = config.get("error_shell", [])
        self.enter_shell = config.get("enter_shell", [])
        self.before_script_enter_shell = config.get("before_script_enter_shell", False)
        self.shell_is_user = config.get("shell_is_user", False)
        all_before = config.get("before_script", [])
        self.before_script = job.get("before_script", all_before)
        self.script = job.get("script", [])
        all_after = config.get("after_script", [])
        self.after_script = job.get("after_script", all_after)
        self.variables = config.get("variables", {})
        job_vars = job.get("variables", {})
        for varname in job_vars:
            self.variables[varname] = job_vars[varname]
        self.tags = job.get("tags", [])
        # prefer needs over dependencies
        self.dependencies = job.get("needs", job.get("dependencies", []))

        if "timeout" in config[self.name]:
            self.timeout_seconds = parse_timeout(config[self.name].get("timeout"))

        self.configure_job_variable("CI_JOB_ID", str(int(time.time())))

        jobname = self.name
        parallel = config[self.name].get("parallel", None)
        if parallel is not None:
            pindex = config.get(".gitlabemu-parallel-index", 1)
            ptotal = config.get(".gitlabemu-parallel-total", 1)
            # set 1 parallel job
            jobname += " {}/{}".format(pindex, ptotal)
            self.configure_job_variable("CI_NODE_INDEX", str(pindex))
            self.configure_job_variable("CI_NODE_TOTAL", str(ptotal))

        self.configure_job_variable("CI_JOB_NAME", jobname)
        self.configure_job_variable("CI_JOB_STAGE", self.stage)
        self.configure_job_variable("CI_JOB_TOKEN", "00" * 32)
        self.configure_job_variable("CI_JOB_URL", "file://gitlab-emulator/none")

    def configure_job_variable(self, name, value):
        """
        Set job variable defaults. If the variable is not present in self.variables, set it to the given value. If the variable is present in os.environ, use that value instead
        :return:
        """
        if value is None:
            value = ""
        value = str(value)

        # set job related env vars
        if name not in self.variables:
            if name in os.environ:
                value = os.environ[name]  # prefer env variables if set
            self.variables[name] = value

    def abort(self):
        """
        Abort the build and attempt cleanup
        :return:
        """
        info("aborting job {}".format(self.name))
        if self.build_process and self.build_process.poll() is None:
            info("killing child build process..")
            os.kill(self.build_process.pid, signal.SIGTERM)

    def check_communicate(self, process, script=None):
        """
        Process STDIO for a build process but raise an exception on error
        :param process: child started by POpen
        :param script: script (eg bytezs) to pipe into stdin
        :return:
        """
        comm(process, stdout=self.stdout, script=script, throw=True)

    def communicate(self, process, script=None):
        """
        Process STDIO for a build process
        :param process: child started by POpen
        :param script: script (eg bytes) to pipe into stdin
        :return:
        """
        comm(process, stdout=self.stdout, script=script)

    def has_bash(self):
        """
        Return True if this system has bash and isn't windows
        """
        if not is_windows():
            return os.path.exists("/bin/bash")
        return False

    def get_envs(self):
        """
        Get environment variable dict for the job
        :return:
        """
        envs = dict(os.environ)
        for name in self.variables:
            value = self.variables[name]
            if value is None:
                value = ""
            envs[name] = str(value)
        return envs

    def run_script(self, lines):
        """
        Execute a script
        :param lines:
        :return:
        """
        envs = self.get_envs()
        envs["PWD"] = os.path.abspath(self.workspace)
        script = make_script(lines, powershell=self.is_powershell())
        opened = subprocess.Popen(self.shell,
                                  env=envs,
                                  cwd=self.workspace,
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
        self.build_process = opened
        self.communicate(opened, script=script.encode())

        return opened.returncode

    def run_shell(self, cmdline=None, run_before=False):
        """
        Execute a shell command on job errors
        :return:
        """
        try:
            print("Running interactive-shell..", flush=True)
            env = self.get_envs()
            prog = ["/bin/sh"]
            if is_windows():
                if "powershell.exe" in self.shell:
                    prog = ["powershell"]
                else:
                    prog = ["cmd.exe"]

            if run_before:
                print("Running before_script..", flush=True)
                # create the before script and run it
                script_file = tempfile.mktemp()
                with open(script_file, "w") as script:
                    script.write(make_script(self.before_script + prog))
                try:
                    subprocess.check_call(["/bin/sh", script_file], env=env, cwd=self.workspace)
                finally:
                    os.unlink(script_file)
                pass
            else:
                subprocess.check_call(prog, env=env)

        except subprocess.CalledProcessError:
            pass

    def shell_on_error(self):
        """
        Execute a shell command on job errors
        :return:
        """
        try:
            print("Job {} script error..".format(self.name), flush=True)
            print("Running error-shell..", flush=True)
            subprocess.check_call(self.error_shell)
        except subprocess.CalledProcessError:
            pass

    def run(self):
        """
        Run the job on the local machine
        :return:
        """
        self.started_time = time.time()
        self.monitor_thread = None

        if self.timeout_seconds and not self.interactive_mode():
            self.monitor_thread = threading.Thread(target=self.monitor_thread_loop, daemon=True)
            try:
                self.monitor_thread.start()
            except RuntimeError as err:
                info("could not create a monitor thread, job timeouts may not work: {}".format(err))
                self.monitor_thread = None

            info("job {} timeout set to {} mins".format(self.name, int(self.timeout_seconds/60)))
            if not self.monitor_thread:
                def alarm_handler(x, y):
                    info("Got SIGALRM, aborting build..")
                    self.abort()

                signal.signal(signal.SIGALRM, alarm_handler)
                signal.alarm(self.timeout_seconds)

        try:
            self.run_impl()
        finally:
            self.ended_time = time.time()
            self.exit_monitor = True
            if self.monitor_thread and self.timeout_seconds:
                self.monitor_thread.join(timeout=5)

    def run_impl(self):
        if self.enter_shell:
            print("Entering shell")
            self.run_shell()
            print("Exiting shell")
            return
        info("running shell job {}".format(self.name))
        lines = self.before_script + self.script
        result = self.run_script(lines)
        if result and self.error_shell:
            self.shell_on_error()
        self.run_script(self.after_script)

        if result:
            fatal("Shell job {} failed".format(self.name))


def make_script(lines, powershell=False):
    """
    Join lines together to make a script
    :param lines:
    :return:
    """
    extra = []
    if platform.system() == "Linux":
        extra = ["set -e"]

    if powershell:
        if platform.system() == "Windows":
            extra = [
                '$ErrorActionPreference = "Continue"',
                'echo "Running on $([Environment]::MachineName)..."'
            ]

    content = os.linesep.join(extra + lines)

    if platform.system() == "Windows":
        content += os.linesep

    return content


