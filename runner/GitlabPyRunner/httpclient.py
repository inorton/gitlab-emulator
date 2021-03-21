"""
OO Wrapper around requests
"""
import sys
from typing import Union, Text, Optional, Any

import requests
from requests.models import Response

from . import consts
from .common import trace_http_request, trace_http_response, trace_http_response_raw


class Session(requests.Session):
    """
    A HTTP user agent complete with cookies
    """
    def __init__(self):
        super(Session, self).__init__()
        pyver = sys.version_info
        pyver_str = "; python {}.{}".format(pyver.major, pyver.minor)
        self.headers["User-Agent"] = consts.USER_AGENT + " " + pyver_str

    def post(self, url, **kwargs) -> Response:
        jdata = kwargs.get("json")
        trace_http_request("post", url, jdata)
        resp = super().post(url, **kwargs)
        trace_http_response_raw(resp)
        return resp

    def json(self, resp):
        data = resp.json()
        trace_http_response(data)
        return data
