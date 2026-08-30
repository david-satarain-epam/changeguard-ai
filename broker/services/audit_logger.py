"""
Audit Logger.
Records every authorization attempt — allowed or blocked.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("changeguard-broker.audit")


class AuditLogger:
    """Structured audit trail for all tool call authorizations."""

    def __init__(self):
        self._logs: list[dict] = []
        self._counter = 0

    def log(
        self,
        agent_id: str,
        tool_name: str,
        session_id: str,
        authorized: bool,
        jit_credential_issued: bool = False,
        credential_ttl: Optional[str] = None,
        reason: Optional[str] = None,
        action: Optional[str] = None,
        token_cost: int = 0,
        target_server: Optional[str] = None,
    ) -> str:
        """
        Record an audit entry.

        Returns the audit_id.
        """
        self._counter += 1
        audit_id = f"call-{self._counter:04d}"

        entry = {
            "audit_id": audit_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
            "tool_name": tool_name,
            "session_id": session_id,
            "authorized": authorized,
            "action_taken": action or ("FORWARDED" if authorized else "BLOCKED"),
        }

        if reason:
            entry["reason"] = reason
        if jit_credential_issued:
            entry["jit_credential_issued"] = True
            entry["credential_ttl"] = credential_ttl
        if token_cost:
            entry["token_cost"] = token_cost
        if target_server:
            entry["target_server"] = target_server

        self._logs.append(entry)

        status = "✅" if authorized else "❌"
        logger.info(
            "%s %s | Agent: %s | Tool: %s | %s",
            status,
            audit_id,
            agent_id,
            tool_name,
            entry["action_taken"],
        )

        return audit_id

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Return the most recent audit entries."""
        return self._logs[-limit:]

    @property
    def last_id(self) -> str:
        """Return the last audit ID."""
        return f"call-{self._counter:04d}"

    @property
    def total_entries(self) -> int:
        """Total audit entries recorded."""
        return len(self._logs)