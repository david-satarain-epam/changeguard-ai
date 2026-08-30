"""
Tool: get_audit_log
Returns recent audit entries.
"""

import logging

logger = logging.getLogger("changeguard-broker.audit")

from services.audit_logger import AuditLogger

def create_audit_handler(audit_logger: AuditLogger):
    """Factory function — injects audit logger."""

    async def get_audit_handler(params: dict, context) -> dict:
        """Return recent audit log entries."""
        limit = params.get("limit", 20)

        entries = audit_logger.get_recent(limit)

        logger.info("Audit log requested: %d entries returned", len(entries))

        return {
            "entries": entries,
            "total": audit_logger.total_entries,
            "returned": len(entries),
        }

    return get_audit_handler