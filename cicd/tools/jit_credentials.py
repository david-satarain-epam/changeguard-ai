"""Validation for broker-issued, short-lived CICD credentials."""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def validate_jit_credential(token: str, expected_tool: str) -> dict[str, Any]:
    """Validate signature, issuer, expiration, and exact tool scope."""
    signing_secret = os.getenv("JIT_SIGNING_SECRET", "")
    if len(signing_secret) < 32:
        raise ValueError("CICD JIT_SIGNING_SECRET must contain at least 32 characters")

    try:
        prefix, encoded_claims, encoded_signature = token.split(".", 2)
        if prefix != "cgjit":
            raise ValueError("unsupported credential format")
        expected_signature = hmac.new(
            signing_secret.encode(), encoded_claims.encode(), hashlib.sha256
        ).digest()
        supplied_signature = _decode(encoded_signature)
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise ValueError("invalid signature")
        claims = json.loads(_decode(encoded_claims))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JIT credential: {exc}") from exc

    if claims.get("iss") != "changeguard-secure-broker":
        raise ValueError("Invalid JIT credential issuer")
    if claims.get("scope") != expected_tool:
        raise ValueError(
            f"JIT credential scope '{claims.get('scope')}' does not allow '{expected_tool}'"
        )
    if int(claims.get("exp", 0)) <= int(time.time()):
        raise ValueError("JIT credential has expired")
    if not claims.get("sub") or not claims.get("session_id") or not claims.get("jti"):
        raise ValueError("JIT credential is missing required claims")
    return claims


def jit_error(token: str, expected_tool: str) -> dict | None:
    """Return a tool-friendly failure result, or None when authorization succeeds."""
    try:
        validate_jit_credential(token, expected_tool)
        return None
    except ValueError as exc:
        return {"status": "FAILED", "error": str(exc), "details": "CICD rejected the JIT credential."}
