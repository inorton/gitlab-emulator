"""
Various functions shared between the other modules
"""
import socket
import zipfile
import os
import yaml
import json
from yaml.constructor import ConstructorError
from gitlabemu.helpers import is_windows

_trace_http = False
_trace_file = os.path.join(os.getcwd(), "http.trace")


def set_trace_http_requests(enable):
    global _trace_http
    _trace_http = enable


def _append_http_trace(message):
    """
    Append the http trace to the log file
    :param message:
    :return:
    """
    with open(_trace_file, "a") as fileh:
        print(str(message) + "---\n", file=fileh)


def trace_http_request(method, url, json_data):
    """
    Log the given json data
    :param method:
    :param url:
    :param json_data:
    :return:
    """
    if _trace_http:
        _append_http_trace("> {} {} json: {}".format(method.upper(), url, json.dumps(json_data)))


def trace_http_response(json_data):
    """
    Log the given json response
    :param json_data:
    :return:
    """
    if _trace_http:
        _append_http_trace("< json: {}".format(json.dumps(json_data)))

def trace_http_response_raw(resp):
    """
    Log the given json response
    :param resp:
    :return:
    """
    if _trace_http:
        _append_http_trace("< raw: status={}".format(resp.status_code))
        if resp.status_code >= 300:
            _append_http_trace("< raw: {}".format(str(resp)))


def gethostname():
    try:
        return socket.gethostname()
    except:
        return "unknown-hostname"


def parse_config(configfile):
    with open(configfile, "r") as infile:
        try:
            config = yaml.load(infile, Loader=yaml.SafeLoader)
        except ConstructorError:
            # this file probably has unicode still in it, use the full loader
            config = yaml.load(infile, Loader=yaml.FullLoader)

    assert config

    assert "server" in config
    assert "dir" in config
    assert "executor" in config
    assert "token" in config
    assert "shell" in config

    return config


def save_config(configfile, data):
    with open("gitlab-runner.yml", "w") as outfile:
        yaml.safe_dump(data, outfile, indent=2)


class ZipFileEx(zipfile.ZipFile):
    """
    A variant of ZipFile that restores file permissions where supported
    """
    # inspired mostly from https://stackoverflow.com/a/39296577/148415

    def _extract_member(self, member, targetpath, pwd):
        """
        Extract a member from the zip file and restore permission bits, also ensure that
        the file is readable and writable by the owner
        :param member:
        :param path:
        :param pwd:
        :return:
        """
        if not isinstance(member, zipfile.ZipInfo):
            member = self.getinfo(member)
        ret_val = super(ZipFileEx, self)._extract_member(member, targetpath, pwd)
        if not is_windows():
            attr = member.external_attr >> 16
            os.chmod(ret_val, attr | 0o600)
        return ret_val


def generate_config(polled):
    """
    Given the polled job response, generate a gitlab-ci yaml file content
    :param polled:
    :return:
    """
    global_config = dict()
    job_config = dict()
    stage = polled["job_info"].get("stage", "test")
    global_config["stages"] = [stage]
    job_config["stage"] = stage
    image = polled["image"]
    if image:
        job_config["image"] = image
    services = polled["services"]
    if services:
        global_config["services"] = services

    if "artifacts" in polled and polled["artifacts"] is not None:
        job_config["artifacts"] = {}
        for item in polled["artifacts"]:
            for element in ["name", "when", "paths", "reports", "expire_in", "exclude"]:
                if element in item:
                    value = item.get(element)
                    if value is not None:
                        job_config["artifacts"][element] = value

    for step in polled["steps"]:
        job_config[step["name"]] = step["script"]

    global_config[polled["job_info"]["name"]] = job_config

    return global_config
