"""
Tool: authorize_tool_call
The main tool of the Secure Broker.
Every tool call from any agent passes through here.
"""

import os
import logging
import httpx

logger = logging.getLogger("changeguard-broker.authorize")

from services.policy_engine import PolicyEngine
from services.jit_credentials import JitCredentialGenerator
from services.audit_logger import AuditLogger

# Services are initialized in server.py and passed via closure

CONTEXT_SERVER_URL = os.getenv("CONTEXT_SERVER_URL", "http://localhost:8081")
CICD_SERVER_URL = os.getenv("CICD_SERVER_URL", "http://localhost:8082")

# Tools that go to Impact Context Server
CONTEXT_TOOLS = {
    "compare_api_contracts",
    "find_affected_consumers",
    "get_business_criticality",
    "get_test_catalog",
}

# Tools that go to Adaptive CI/CD Server
EXECUTION_TOOLS = {
    "run_tests",
    "deploy_canary",
    "monitor",
    "deploy_full",
    "rollback",
}


def _get_target_server(tool_name: str) -> str:
    """Map tool name to target server URL."""
    if tool_name in CONTEXT_TOOLS:
        return CONTEXT_SERVER_URL
    if tool_name in EXECUTION_TOOLS:
        return CICD_SERVER_URL
    return None


def create_authorize_handler(
    policy_engine: PolicyEngine,
    jit_creds: JitCredentialGenerator,
    audit_logger: AuditLogger,
):
    """Factory function — injects services."""

    async def authorize_handler(params: dict, context) -> dict:
        """
        Authorize a tool call from an agent.

        1. Check policy: is agent + tool allowed?
        2. If blocked → audit + return
        3. If allowed → issue JIT credential → audit → forward
        """
        agent_id = params.get("agent_id", "unknown")
        tool_name = params.get("tool_name", "")
        session_id = params.get("session_id", "unknown")
        payload = params.get("payload", {})

        logger.info("━" * 60)
        logger.info("Authorization request: agent=%s tool=%s", agent_id, tool_name)

        # ── Step 1: Policy check ──
        allowed, reason = policy_engine.is_allowed(agent_id, tool_name)

        if not allowed:
            audit_logger.log(
                agent_id=agent_id,
                tool_name=tool_name,
                session_id=session_id,
                authorized=False,
                reason=reason,
                action="BLOCKED",
            )
            return {
                "authorized": False,
                "reason": reason,
                "action_taken": "BLOCKED",
                "audit_id": audit_logger.last_id,
            }

        # ── Step 2: Issue JIT credential ──
        credential = jit_creds.generate(
            agent_id=agent_id,
            tool_name=tool_name,
        )

        # ── Step 3: Determine target server ──
        target = _get_target_server(tool_name)

        # ── Step 4: Audit log ──
        audit_logger.log(
            agent_id=agent_id,
            tool_name=tool_name,
            session_id=session_id,
            authorized=True,
            jit_credential_issued=True,
            credential_ttl=credential["expires_at"],
            action="FORWARDED",
            target_server=target,
        )

        # ── Step 5: Forward to target (Layer 2) ──
        # In Layer 1 (standalone), we return the authorization.
        # In Layer 2 (connected), the Broker forwards the call.
        forward_result = None
        if target:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        f"{target}/{tool_name}",
                        json={"payload": payload, "audit_id": audit_logger.last_id},
                    )
                    forward_result = response.json() if response.status_code == 200 else None
            except Exception as e:
                logger.error("Forward failed: %s", e)
                forward_result = {"error": str(e)}

        return {
            "authorized": True,
            "jit_credential": credential["token"],
            "credential_ttl": credential["expires_at"],
            "audit_id": audit_logger.last_id,
            "forwarded_to": target,
            "forward_result": forward_result,
        }

    return authorize_handler