"""
JIT Credential Generator.
Generates temporary, scoped credentials valid for 15 minutes.
"""

import base64
import hashlib
import hmac
import json
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("changeguard-broker.jit")


class JitCredentialGenerator:
    """Generates just-in-time credentials scoped to a single tool call."""

    def __init__(self, default_ttl_minutes: int = 15, signing_secret: str = None):
        self.default_ttl = default_ttl_minutes
        self.signing_secret = signing_secret or os.getenv("JIT_SIGNING_SECRET", "")
        if len(self.signing_secret) < 32:
            raise ValueError("JIT_SIGNING_SECRET must contain at least 32 characters")

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    def generate(
        self,
        agent_id: str,
        tool_name: str,
        session_id: str,
        ttl_minutes: int = None,
    ) -> dict:
        """
        Generate a JIT credential.

        Returns dict with token, scope, timestamps.
        """
        if ttl_minutes is None:
            ttl_minutes = self.default_ttl

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=ttl_minutes)
        claims = {
            "iss": "changeguard-secure-broker",
            "sub": agent_id,
            "scope": tool_name,
            "session_id": session_id,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": uuid.uuid4().hex,
        }
        encoded_claims = self._encode(
            json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
        )
        signature = hmac.new(
            self.signing_secret.encode(), encoded_claims.encode(), hashlib.sha256
        ).digest()
        token = f"cgjit.{encoded_claims}.{self._encode(signature)}"

        credential = {
            "token": token,
            "agent_id": agent_id,
            "scope": tool_name,
            "session_id": session_id,
            "jti": claims["jti"],
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "ttl_minutes": ttl_minutes,
        }

        logger.info(
            "JIT credential issued: %s for agent '%s' (tool: %s, expires: %s)",
            token[:20] + "...",
            agent_id,
            tool_name,
            expires_at.strftime("%H:%M:%S"),
        )

        return credential