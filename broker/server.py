"""
ChangeGuard AI Secure Broker — MCP Server
=================================
The gatekeeper. Every tool call from any agent passes through here.

What it does:
  - Receives tool calls from agents via MCP
  - Checks policies (is this agent allowed to call this tool?)
  - Issues JIT credentials (15 min TTL, scoped to the tool)
  - Logs EVERYTHING to the audit trail
  - Forwards authorized calls to the target MCP server
  - Blocks unauthorized calls immediately

Usage:
  python server.py
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("changeguard-broker")

from mcp.server.mcpserver import MCPServer
from services.policy_engine import PolicyEngine
from services.jit_credentials import JitCredentialGenerator
from services.audit_logger import AuditLogger
from tools.authorize import create_authorize_handler
from tools.audit import create_audit_handler

# ═══════════════════════════════════════════════════════════════
# INIT SERVICES
# ═══════════════════════════════════════════════════════════════

policy_engine = PolicyEngine()
jit_creds = JitCredentialGenerator(default_ttl_minutes=15)
audit_logger = AuditLogger()

logger.info("Services initialized: %d policies loaded", len(policy_engine.policies))

# ═══════════════════════════════════════════════════════════════
# MCP SERVER
# ═══════════════════════════════════════════════════════════════

server = MCPServer("secure-broker")

# Register tools
@server.tool()
async def authorize_tool_call(
    agent_id: str,
    tool_name: str,
    session_id: str,
    payload: dict = None,
) -> dict:
    """
    Authorize a tool call from an agent.
    Checks policy, issues JIT credential, logs audit entry.
    Blocks unauthorized agents and tools.
    """
    handler = create_authorize_handler(policy_engine, jit_creds, audit_logger)
    return await handler(
        {
            "agent_id": agent_id,
            "tool_name": tool_name,
            "session_id": session_id,
            "payload": payload or {},
        },
        context=None,
    )


@server.tool()
async def get_audit_log(limit: int = 20) -> dict:
    """Return recent audit log entries."""
    handler = create_audit_handler(audit_logger)
    return await handler({"limit": limit}, context=None)


logger.info("Tools registered: authorize_tool_call, get_audit_log")

# ═══════════════════════════════════════════════════════════════
# START
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    logger.info("=" * 60)
    transport_type = os.getenv("MCP_TRANSPORT", "streamable-http")
    logger.info("🛡️  ChangeGuard AI Secure Broker starting on %s transport", transport_type)
    logger.info("=" * 60)
    server.run(transport=transport_type, host="0.0.0.0", port=port)