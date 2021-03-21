"""
Functions for adding gitlab-runner.py as a service.
"""
from __future__ import print_function
import os
import shutil
from .common import parse_config


class BaseService(object):
    """
    Base service implementations
    """

    def detect(self):
        """
        Check that this service system is supported
        :return:
        """
        return False

    def is_installed(self, config):
        """
        :param config: path to the configuration used.
        :return: True if already installed
        """
        return False

    def install(self, config, user):
        raise NotImplementedError()

    def uninstall(self):
        raise NotImplementedError()

    def configure(self, configfile, user):
        """ write the shell config file
        """
        confdir = "/etc/gitlab-python-runner/"
        config = parse_config(configfile)
        if not os.path.exists(confdir):
            os.makedirs(confdir)
        assert configfile and config
        shutil.copyfile(configfile, os.path.join(confdir, "gitlab-runner.yml"))
        if user is None:
            user = "gitlab-runner"
        logfile = os.path.join(config["dir"], "runner.log")

        shellfile = "/etc/gitlab-python-runner/service.conf"

        with open(shellfile, "w") as outfile:
            outfile.write("""
RUNNER_USER={}
LOGFILE={}
export RUNNER_USER
export LOGFILE            
            """.format(user, logfile))
        return user


class SystemV(BaseService):
    """
    Install/Uninstall service on using SysV
    """
    START = "S90gitlab-python-runner"
    STOP = "K90gitlab-python-runner"

    INIT_SCRIPT = os.path.join(os.path.dirname(__file__), "gitlab-runner-init.sh")
    ETC_INIT = "/etc/init.d/gitlab-python-runner"

    def install(self, config, user):
        user = self.configure(config, user)
        print("Installing config {} as user {}".format(config, user))
        if os.path.exists(self.ETC_INIT):
            os.unlink(self.ETC_INIT)
        shutil.copyfile(self.INIT_SCRIPT, self.ETC_INIT)
        os.chmod(self.ETC_INIT, 0o755)
        for i in [2]:
            os.symlink(self.ETC_INIT, os.path.join("/etc/rc{}.d".format(i), self.START))
        for i in [0]:
            os.symlink(self.ETC_INIT, os.path.join("/etc/rc{}.d".format(i), self.STOP))

    def is_installed(self, config):
        return os.path.exists(os.path.join("/etc", "rc2.d", self.START))

    def uninstall(self):
        for i in [2]:
            filename = os.path.join("/etc/rc{}.d".format(i), self.START)
            if os.path.exists(filename):
                os.unlink(filename)
        for i in [0]:
            filename = os.path.join("/etc/rc{}.d".format(i), self.STOP)
            if os.path.exists(filename):
                os.unlink(filename)
        if os.path.exists(self.ETC_INIT):
            os.unlink(self.ETC_INIT)

    def detect(self):
        required = ["/etc/rc2.d", "/etc/init.d", "/etc/rc0.d"]
        for item in required:
            if not os.path.exists(item):
                return False
        return True


def get_installer():
    for test in [SystemV()]:
        if test.detect():
            return test
    return None
