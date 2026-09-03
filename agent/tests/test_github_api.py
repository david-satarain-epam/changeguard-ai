import json
import urllib.error

import pytest

from tools.github_api import fetch_github_pr


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_fetch_github_pr_rejects_merged_pr(monkeypatch):
    monkeypatch.setattr(
        "tools.github_api.urllib.request.urlopen",
        lambda request, timeout: FakeResponse({"state": "closed", "merged_at": "2026-09-02T12:00:00Z"}),
    )

    with pytest.raises(ValueError, match="already merged"):
        fetch_github_pr("https://github.com/example/payments-api/pull/1")


def test_fetch_github_pr_rejects_closed_pr(monkeypatch):
    monkeypatch.setattr(
        "tools.github_api.urllib.request.urlopen",
        lambda request, timeout: FakeResponse({"state": "closed", "merged_at": None}),
    )

    with pytest.raises(ValueError, match="is closed"):
        fetch_github_pr("https://github.com/example/payments-api/pull/1")


def test_fetch_github_pr_reports_missing_pr(monkeypatch):
    def raise_not_found(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr("tools.github_api.urllib.request.urlopen", raise_not_found)

    with pytest.raises(ValueError, match="was not found"):
        fetch_github_pr("https://github.com/example/payments-api/pull/999")
