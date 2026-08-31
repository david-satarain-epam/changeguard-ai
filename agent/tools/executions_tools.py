"""MCP toolset for the Secure Broker execution gateway."""

import logging
import os

from google.adk.tools import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

logger = logging.getLogger("changeguard-agent.execution")

BROKER_MCP_URL = os.getenv(
    "BROKER_MCP_URL",
    "https://changeguard-broker-511412396970.us-east1.run.app/mcp",
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

# Compatibility exports. These all point to the broker; direct CICD access is
# intentionally unavailable to the agent.
execution_toolset = broker_toolset
run_tests_tool = broker_toolset
deploy_canary_tool = broker_toolset
monitor_tool = broker_toolset
deploy_full_tool = broker_toolset
rollback_tool = broker_toolset