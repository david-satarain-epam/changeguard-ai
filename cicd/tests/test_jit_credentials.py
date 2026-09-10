"""Tests for broker-issued JIT credential enforcement in CICD."""

import base64
import hashlib
import hmac
import json
import time

import pytest

from tools.jit_credentials import validate_jit_credential


SECRET = "test-jit-signing-secret-at-least-32-chars"


def issue_token(scope: str, expires_at: int | None = None) -> str:
    claims = {
        "iss": "changeguard-secure-broker",
        "sub": "change-impact-agent",
        "scope": scope,
        "session_id": "pr-847",
        "iat": int(time.time()),
        "exp": expires_at or int(time.time()) + 60,
        "jti": "test-credential-id",
    }
    encoded_claims = base64.urlsafe_b64encode(
        json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
    ).decode().rstrip("=")
    signature = hmac.new(SECRET.encode(), encoded_claims.encode(), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"cgjit.{encoded_claims}.{encoded_signature}"


def test_accepts_valid_scoped_credential(monkeypatch):
    monkeypatch.setenv("JIT_SIGNING_SECRET", SECRET)
    claims = validate_jit_credential(issue_token("run_tests"), "run_tests")
    assert claims["sub"] == "change-impact-agent"
    assert claims["session_id"] == "pr-847"


def test_rejects_wrong_tool_scope(monkeypatch):
    monkeypatch.setenv("JIT_SIGNING_SECRET", SECRET)
    with pytest.raises(ValueError, match="does not allow"):
        validate_jit_credential(issue_token("run_tests"), "deploy_full")


def test_rejects_tampered_credential(monkeypatch):
    monkeypatch.setenv("JIT_SIGNING_SECRET", SECRET)
    token = issue_token("run_tests")
    with pytest.raises(ValueError, match="invalid signature"):
        validate_jit_credential(token[:-1] + ("A" if token[-1] != "A" else "B"), "run_tests")


def test_rejects_expired_credential(monkeypatch):
    monkeypatch.setenv("JIT_SIGNING_SECRET", SECRET)
    with pytest.raises(ValueError, match="expired"):
        validate_jit_credential(issue_token("run_tests", int(time.time()) - 1), "run_tests")
