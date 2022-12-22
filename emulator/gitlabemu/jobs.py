"""
Represent a gitlab job
"""
import os
import shutil
import signal

import sys
import subprocess
import tempfile
import threading
import time
from typing import Optional, Dict, List, Union, Any

from .artifacts import GitlabArtifacts
from .logmsg import info, fatal, debugrule
from .errors import GitlabEmulatorError
from .helpers import communicate as comm, is_windows, is_apple, is_linux, debug_print, parse_timeout, powershell_escape
from .ansi import ANSI_GREEN, ANSI_RESET
from .ruleparser import evaluate_rule
from .variables import expand_variable
from .gitlab.constraints import JOB_PERSISTED_VARIABLES, PIPELINE_PERSISTED_VARIABLES


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
        self.extra_variables = {}
        self.allow_add_variables = True
        self.dependencies = []
        self.needed_artifacts = []
        self.artifacts = GitlabArtifacts()
        self._shell = None
        self._parallel = None
        self._config = {}
        if is_windows():  # pragma: linux no cover
            self._shell = "powershell"
        else:
            self._shell = "sh"

        self.workspace = None
        self.stderr = sys.stderr
        self.stdout = sys.stdout
        self.started_time = 0
        self.ended_time = 0
        self.timeout_seconds = 0
        self.monitor_thread = None
        self.exit_monitor = False
        self.skipped_reason = None
        self.rules = None
        self.configloader = None

    def copy_config(self) -> dict:
        return dict(self._config)

    def check_skipped(self) -> bool:
        """Return True if this job is skipped by rules"""
        return self.skipped_reason is not None

    def interactive_mode(self):
        """Return True if in interactive mode"""
        return self.enter_shell or self.before_script_enter_shell

    def __str__(self):
        return "job {}".format(self.name)

    def duration(self):
        if self.started_time:
            ended = self.ended_time
            if not ended:
                ended = time.time()
            return ended - self.started_time
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
        return "powershell" == self.shell

    @property
    def shell(self):
        return self._shell

    @shell.setter
    def shell(self, value):
        if value not in ["cmd", "powershell", "sh"]:
            raise NotImplementedError("Unsupported shell type " + value)
        self._shell = value

    def shell_command(self, scriptfile):
        if is_windows():  # pragma: linux no cover
            if self.shell == "powershell":
                return ["powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-ExecutionPolicy", "Bypass",
                        "-Command", scriptfile]
            return ["powershell", "-Command", "& cmd /Q /C " + scriptfile]
        # else unix/linux
        interp = "/bin/sh"
        if self.has_bash():
            interp = "/bin/bash"
        return [interp, scriptfile]

    @property
    def parallel(self) -> Optional[int]:
        return self._parallel

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
        self.variables = dict(job.get("variables", {}))
        self.extra_variables = dict(config.get(".gle-extra_variables", {}))
        self.tags = job.get("tags", [])
        # prefer needs over dependencies
        needed = job.get("needs", job.get("dependencies", []))
        self.dependencies = []
        for item in needed:
            if isinstance(item, dict):
                self.dependencies.append(item.get("job"))
                if item.get("artifacts", False):
                    self.needed_artifacts.append(item.get("job"))
            else:
                self.dependencies.append(item)
                self.needed_artifacts.append(item)
        self.dependencies = list(set(self.dependencies))

        if "timeout" in config[self.name]:
            self.timeout_seconds = parse_timeout(config[self.name].get("timeout"))

        parallel = config[self.name].get("parallel", None)
        self._parallel = parallel
        self._config = dict(config)
        self.set_job_variables()
        self.artifacts.load(dict(job.get("artifacts", {})))

        # load and match the rules
        if self.configloader:
            rules = config[self.name].get("rules", [])
            if rules:
                if not isinstance(rules, list):
                    raise SyntaxError(f"error parsing rules in job {self.name}")
                for rule_item in rules:
                    rule_item: dict
                    # each should be a dict,
                    debugrule(f"job={self.name}: checking rule: {rule_item}")
                    if "if" in rule_item:
                        # match it now
                        if_matched = evaluate_rule(rule_item["if"], self.configloader.variables)
                    else:
                        # is a bare rule with no "if", usually this is the last rule
                        if_matched = True

                    if if_matched:
                        debugrule(f"job={self.name}: rule matched")
                        when = rule_item.get("when", "on_success")
                        if when:
                            if when == "never":
                                self.skipped_reason = f"matched {rule_item}"
                        # take the first hit
                        break

    def get_config(self, name: str):
        return self._config.get(name)

    def set_job_variables(self):
        self.configure_job_variable("CI_JOB_ID", str(int(time.time())), force=True)
        self.configure_job_variable("CI_CONFIG_PATH", self.get_config("ci_config_file"))
        self.configure_job_variable("CI_PROJECT_DIR", self.workspace)
        self.configure_job_variable("CI_BUILDS_DIR", os.path.dirname(self.workspace))
        jobname = self.name
        if self._parallel is not None:
            pindex = self._config.get(".gitlabemu-parallel-index", 1)
            ptotal = self._config.get(".gitlabemu-parallel-total", 1)
            # set 1 parallel job
            jobname += " {}/{}".format(pindex, ptotal)
            self.configure_job_variable("CI_NODE_INDEX", str(pindex), force=True)
            self.configure_job_variable("CI_NODE_TOTAL", str(ptotal), force=True)

        self.configure_job_variable("CI_JOB_NAME", jobname, force=True)
        self.configure_job_variable("CI_JOB_STAGE", self.stage, force=True)
        self.configure_job_variable("CI_JOB_TOKEN", "00" * 32)
        self.configure_job_variable("CI_JOB_URL", "file://gitlab-emulator/none")

    def configure_job_variable(self, name, value, force=False):
        """
        Set job variable defaults. If the variable is not present in self.extra_variables, set it to the given value. If the variable is present in os.environ, use that value instead
        :return:
        """
        if not self.allow_add_variables:
            return

        if value is None:
            value = ""
        value = str(value)

        if force:
            self.extra_variables[name] = value
        else:
            # set job related env vars
            if name not in self.extra_variables:
                if name in os.environ:
                    value = os.environ[name]  # prefer env variables if set
                self.extra_variables[name] = value

    def abort(self):
        """
        Abort the build and attempt cleanup
        :return:
        """
        info("aborting job {}".format(self.name))
        if self.build_process and self.build_process.poll() is None:
            info("killing child build process..")
            os.kill(self.build_process.pid, signal.SIGTERM)
            killing = time.time()
            while self.build_process.poll() is None: # pragma: no cover
                time.sleep(1)
                if time.time() - killing > 10:
                    os.kill(self.build_process.pid, signal.SIGKILL)

    def check_communicate(self, process, script=None):
        """
        Process STDIO for a build process but raise an exception on error
        :param process: child started by POpen
        :param script: script (eg bytes) to pipe into stdin
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
        return False  # pragma: linux no cover

    def base_variables(self) -> Dict[str, str]:
        return dict(self._config.get("variables", {}))

    @staticmethod
    def ci_expandable_variables(variables: Dict[str, str]) -> Dict[str, str]:
        expandable = {}
        for name in variables:
            if name in PIPELINE_PERSISTED_VARIABLES + JOB_PERSISTED_VARIABLES:
                expandable[name] = variables[name]
        return expandable

    def expand_variables(self, variables: Dict[str, str], only_ci=True) -> Dict[str, str]:
        expanded = {}
        for name in variables:
            value = variables[name]
            if only_ci:
                value = expand_variable(self.ci_expandable_variables(variables), value)
            else:
                value = expand_variable(variables, value)
            expanded[name] = value
        return expanded

    def get_envs(self, expand_only_ci=True):
        """
        Get environment variable dict for the job
        :return:
        """
        envs = self.base_variables()
        envs.update(os.environ)

        for name in self.variables:
            value = self.variables[name]
            if value is None:
                value = ""
            envs[name] = str(value)
        for name in self.extra_variables:
            envs[name] = self.extra_variables[name]
        # expand any predefeined variables
        return self.expand_variables(envs, only_ci=expand_only_ci)

    def get_script_fileext(self):
        ext = ".sh"
        if is_windows():  # pragma: linux no cover
            if self.is_powershell():
                ext = ".ps1"
            else:
                ext = ".bat"
        return ext

    def run_script(self, lines):
        """
        Execute a script
        :param lines:
        :return:
        """
        envs = self.get_envs()
        envs["PWD"] = os.path.abspath(self.workspace)
        script = make_script(lines, powershell=self.is_powershell())
        temp = tempfile.mkdtemp()
        try:
            ext = self.get_script_fileext()
            generated = os.path.join(temp, "generated-gitlab-script" + ext)
            with open(generated, "w") as fd:
                print(script, file=fd)
            cmdline = self.shell_command(generated)
            debug_print("cmdline: {}".format(cmdline))
            opened = subprocess.Popen(cmdline,
                                      env=envs,
                                      shell=False,
                                      cwd=self.workspace,
                                      stdin=subprocess.DEVNULL,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT)
            self.build_process = opened
            self.communicate(opened, script=None)
        finally:
            shutil.rmtree(temp)

        return opened.returncode

    def run_shell(self, cmdline=None, run_before=False):
        """
        Execute a shell command on job errors
        :return:
        """
        # this is interactive only and cant really be easily tested
        # pragma: no cover
        try:
            print("Running interactive-shell..", flush=True)
            env = self.get_envs()
            prog = ["/bin/sh"]
            if is_windows():  # pragma: linux no cover
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
        # this is interactive only and cant really be easily tested
        # pragma: no cover
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
                # funky hpux special case
                # pragma: no cover
                info("could not create a monitor thread, job timeouts may not work: {}".format(err))
                self.monitor_thread = None

            info("job {} timeout set to {} mins".format(self.name, int(self.timeout_seconds/60)))
            if not self.monitor_thread:
                # funky hpux special case
                # pragma: no cover
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
        if self.enter_shell:  # pragma: no cover
            # interactive mode only
            print("Entering shell")
            self.run_shell()
            print("Exiting shell")
            return
        info("running shell job {}".format(self.name))
        lines = self.before_script + self.script
        result = self.run_script(lines)
        if result and self.error_shell:  # pragma: no cover
            self.shell_on_error()
        if self.after_script:
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
    tail = []

    line_wrap_before = []
    line_wrap_tail = []

    if is_linux() or is_apple():
        extra = ["set -e"]

    if is_windows():  # pragma: linux no cover
        if powershell:
            extra = [
                '$ErrorActionPreference = "Stop"',
                'echo ...',
                'echo "Running on $([Environment]::MachineName)..."',
            ]
            line_wrap_before = [
                '& {' + os.linesep,
            ]
            line_wrap_tail = [
                '}' + os.linesep,
                'if(!$?) { Exit $LASTEXITCODE }' + os.linesep,
            ]
        else:
            extra = [
                '@echo off',
                'setlocal enableextensions',
                'setlocal enableDelayedExpansion',
                'set nl=^',
                'echo ...',
                'echo Running on %COMPUTERNAME%...',
                'echo Warning: cmd shells on windows are no longer supported by gitlab',
                'call :buildscript',
                'if !errorlevel! NEQ 0 exit /b !errorlevel!',
                'goto :EOF',
                ':buildscript',
            ]
            line_wrap_tail = [
            ]

            tail = [
                'goto :EOF',
            ]
    else:
        powershell = False

    content = os.linesep.join(extra) + os.linesep
    for line in lines:
        if "\n" in line:
            content += line
        else:
            content += os.linesep.join(line_wrap_before)
            if powershell:  # pragma: linux no cover
                content += f"echo {powershell_escape(ANSI_GREEN + line + ANSI_RESET, variables=True)}" + os.linesep
                content += "& " + line + os.linesep
                content += "if(!$?) { Exit $LASTEXITCODE }" + os.linesep
            else:
                content += line + os.linesep
            content += os.linesep.join(line_wrap_tail)
    for line in tail:
        content += line

    if is_windows():  # pragma: linux no cover
        content += os.linesep

    return content
