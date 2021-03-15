"""
Tests for GitlabPyRunner.httpclient
"""
from GitlabPyRunner import httpclient


def test_get():
    """
    Test that we wrapper GET properly
    :return:
    """

    client = httpclient.Session()
    resp = client.get("https://www.google.com/robots.txt")
    assert resp