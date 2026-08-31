"""Execution tools connected to the Secure Broker via ADK MCPToolset."""

import logging
import os

from google.adk.tools import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

logger = logging.getLogger("changeguard-agent.execution")

BROKER_MCP_URL = os.getenv("BROKER_MCP_URL", "https://changeguard-broker-cen47pzzba-ue.a.run.app/mcp")
BROKER_MCP_HEADERS = {}
if token := os.getenv("BROKER_MCP_TOKEN"):
    BROKER_MCP_HEADERS["Authorization"] = f"Bearer {token}"

execution_toolset = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=BROKER_MCP_URL,
        headers=BROKER_MCP_HEADERS or None,
        timeout=30.0,
        sse_read_timeout=300.0,
        terminate_on_close=True,
    ),
    tool_filter=[
        "run_tests",
        "deploy_canary",
        "monitor",
        "deploy_full",
        "rollback",
    ],
)

logger.info("Execution MCP toolset configured for broker URL: %s", BROKER_MCP_URL)

run_tests_tool = execution_toolset
deploy_canary_tool = execution_toolset
monitor_tool = execution_toolset
deploy_full_tool = execution_toolset
rollback_tool = execution_toolset