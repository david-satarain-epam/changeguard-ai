"""MCP toolset for the Secure Broker execution gateway."""

import logging
import os
import json

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from google.adk.tools import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

logger = logging.getLogger("changeguard-agent.execution")

BROKER_MCP_URL = os.getenv(
    "BROKER_MCP_URL",
    "http://localhost:8080/mcp",
)
BROKER_MCP_HEADERS = {}
if token := os.getenv("BROKER_MCP_TOKEN"):
    BROKER_MCP_HEADERS["Authorization"] = f"Bearer {token}"

broker_toolset = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=BROKER_MCP_URL,
        headers=BROKER_MCP_HEADERS or None,
        timeout=30.0,
        sse_read_timeout=300.0,
        terminate_on_close=True,
    ),
    tool_filter=["authorize_tool_call", "get_audit_log"],
)

logger.info("Broker MCP toolset configured: %s", BROKER_MCP_URL)


async def call_broker(tool_name: str, payload: dict, session_id: str) -> dict:
    """Authorize and execute one CI/CD operation through the broker MCP."""
    arguments = {
        "agent_id": "change-impact-agent",
        "tool_name": tool_name,
        "session_id": session_id,
        "payload": payload,
    }
    async with httpx.AsyncClient(
        headers=BROKER_MCP_HEADERS or None,
        timeout=120,
    ) as http_client:
        async with streamable_http_client(
            BROKER_MCP_URL,
            http_client=http_client,
        ) as streams:
            read_stream, write_stream = streams[:2]
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "authorize_tool_call",
                    arguments=arguments,
                )

    if getattr(result, "isError", False):
        return {"authorized": False, "error": "Broker MCP returned an error"}
    for content in getattr(result, "content", []):
        text = getattr(content, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"authorized": False, "error": text}
    return {"authorized": False, "error": "Broker returned no result"}

# Compatibility exports. These all point to the broker; direct CICD access is
# intentionally unavailable to the agent.
execution_toolset = broker_toolset
run_tests_tool = broker_toolset
deploy_canary_tool = broker_toolset
monitor_tool = broker_toolset
deploy_full_tool = broker_toolset
rollback_tool = broker_toolset