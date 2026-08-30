"""
JIT Credential Generator.
Generates temporary, scoped credentials valid for 15 minutes.
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("changeguard-broker.jit")


class JitCredentialGenerator:
    """Generates just-in-time credentials scoped to a single tool call."""

    def __init__(self, default_ttl_minutes: int = 15):
        self.default_ttl = default_ttl_minutes

    def generate(
        self,
        agent_id: str,
        tool_name: str,
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
        token = f"changeguard-jit-{uuid.uuid4().hex[:16]}"

        credential = {
            "token": token,
            "agent_id": agent_id,
            "scope": tool_name,
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