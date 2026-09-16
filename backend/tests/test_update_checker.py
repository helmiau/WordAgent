import json
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from gui.views import home_interface

API_URLS = ("https://official.example/releases/latest", "https://mirror.example/releases/latest")
RELEASE_URL = "https://github.com/visresearch/WordAgent/releases/latest"
RELEASE = json.dumps({"tag_name": " v0.6.2 ", "html_url": "https://mirror.example/download"}).encode()


def install_responses(monkeypatch, responses):
    requests = []

    def open_url(request, timeout):
        requests.append(request.full_url)
        assert timeout == 8
        assert request.get_header("Accept") == "application/vnd.github+json"
        response = responses[len(requests) - 1]
        if isinstance(response, Exception):
            raise response
        return BytesIO(response)

    monkeypatch.setattr(home_interface, "urlopen", open_url)
    return requests


def test_official_success_does_not_request_mirror(monkeypatch):
    requests = install_responses(monkeypatch, [RELEASE])
    result = home_interface.check_latest_release(API_URLS, release_url=RELEASE_URL)
    assert requests == [API_URLS[0]]
    assert result == {"ok": True, "latest_tag": "v0.6.2", "latest_url": RELEASE_URL, "error": ""}


@pytest.mark.parametrize(
    "failure",
    [
        URLError("connection refused"),
        TimeoutError("timed out"),
        HTTPError(API_URLS[0], 403, "rate limited", {}, None),
        b"<html>proxy landing page</html>",
        b"\xff",
        b"[]",
        b"null",
        b"{}",
        b'{"tag_name": ""}',
        b'{"tag_name": "unknown"}',
        b'{"tag_name": 123}',
    ],
)
def test_failed_or_invalid_response_tries_next_api(monkeypatch, failure):
    requests = install_responses(monkeypatch, [failure, RELEASE])
    result = home_interface.check_latest_release(API_URLS, release_url=RELEASE_URL)
    assert requests == list(API_URLS)
    assert result["ok"] is True
    assert result["latest_tag"] == "v0.6.2"
    assert result["latest_url"] == RELEASE_URL
    assert result["error"] == ""


def test_all_apis_fail_without_reporting_latest_version(monkeypatch):
    requests = install_responses(monkeypatch, [TimeoutError("timed out"), b"{}"])
    result = home_interface.check_latest_release(API_URLS, release_url=RELEASE_URL)
    assert requests == list(API_URLS)
    assert result["ok"] is False
    assert result["latest_tag"] == ""
    assert all(url in result["error"] for url in API_URLS)
