"""
Tool: authorize_tool_call
The main tool of the Secure Broker.
Every tool call from any agent passes through here.
"""

import os
import logging
import json

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger("changeguard-broker.authorize")

try:
    from services.policy_engine import PolicyEngine
    from services.jit_credentials import JitCredentialGenerator
    from services.audit_logger import AuditLogger
except ModuleNotFoundError:  # pragma: no cover
    from broker.services.policy_engine import PolicyEngine
    from broker.services.jit_credentials import JitCredentialGenerator
    from broker.services.audit_logger import AuditLogger

# Services are initialized in server.py and passed via closure

CICD_MCP_URL = os.getenv("CICD_MCP_URL", "http://localhost:8082/mcp")
CICD_MCP_HEADERS = {}
if token := os.getenv("CICD_MCP_TOKEN"):
    CICD_MCP_HEADERS["Authorization"] = f"Bearer {token}"

# Tools that go to Adaptive CI/CD Server
EXECUTION_TOOLS = {
    "run_tests",
    "comment_pr",
    "merge_pr",
    "deploy_canary",
    "monitor",
    "deploy_full",
    "rollback",
}


def _get_target_server(tool_name: str) -> str:
    """Map tool name to target server URL."""
    if tool_name in EXECUTION_TOOLS:
        return CICD_MCP_URL
    return None


def _mcp_endpoint(url: str) -> str:
    """Normalize a configured CICD URL to the streamable HTTP endpoint."""
    return url if url.rstrip("/").endswith("/mcp") else f"{url.rstrip('/')}/mcp"


async def _call_cicd_tool(tool_name: str, payload: dict) -> dict:
    """Forward an authorized operation through CICD's MCP protocol."""
    async with httpx.AsyncClient(
        headers=CICD_MCP_HEADERS or None,
        timeout=120,
    ) as http_client:
        async with streamable_http_client(
            _mcp_endpoint(CICD_MCP_URL),
            http_client=http_client,
        ) as streams:
            read_stream, write_stream = streams[:2]
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=payload)

    if getattr(result, "isError", False):
        return {"error": f"CICD MCP tool '{tool_name}' returned an error"}
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured

    for content in getattr(result, "content", []):
        text = getattr(content, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"result": text}
    return {}


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
        if tool_name in EXECUTION_TOOLS:
            try:
                forward_result = await _call_cicd_tool(tool_name, payload)
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