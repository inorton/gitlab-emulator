"""Tests for stream_response.py"""

import requests
from ..stream_response import ResponseStream


def test_seekable_response():
    resp = requests.get("https://rfc-editor.org/rfc/rfc2549.txt")
    resp.raise_for_status()
    seekable = ResponseStream(resp.iter_content(512))

    assert seekable.seekable()

    chunk = seekable.read(512)
    assert len(chunk) == 512
    assert seekable.tell() == 512

    seekable.seek(0)
    chunk2 = seekable.read(512)
    assert chunk == chunk2

    seekable.seek(0)
    full = seekable.read()
    assert chunk in full
