"""
Execution tools — Call Secure Broker → Adaptive CI/CD Server.

The agent delegates execution through these tools.
In Layer 1: mock responses.
In Layer 2: MCP calls to Secure Broker.
"""

import logging
from google.adk.tools import MCPTool, ToolContext

logger = logging.getLogger("changeguard-agent.execution")


# ═══════════════════════════════════════════════════════════════
# run_tests
# ═══════════════════════════════════════════════════════════════

async def run_tests_handler(params: dict, context: ToolContext) -> dict:
    """Execute test suite."""
    test_plan = params.get("test_plan", [])
    pr_id = params.get("pr_id", "")

    logger.info("run_tests: %d tests for PR %s", len(test_plan), pr_id)

    return {
        "total": len(test_plan),
        "passed": len(test_plan),
        "failed": 0,
        "duration_sec": len(test_plan) * 1.1,
        "details": f"{len(test_plan)}/{len(test_plan)} passed",
        "pr_id": pr_id,
        "mode": "simulated",
    }


run_tests_tool = MCPTool(
    name="run_tests",
    description="Execute a test suite via the Adaptive CI/CD Server. Passes through Secure Broker.",
    handler=run_tests_handler,
    input_schema={
        "type": "object",
        "properties": {
            "test_plan": {"type": "array", "items": {"type": "string"}},
            "pr_id": {"type": "string"},
        },
        "required": ["test_plan", "pr_id"],
    },
)


# ═══════════════════════════════════════════════════════════════
# deploy_canary
# ═══════════════════════════════════════════════════════════════

async def deploy_canary_handler(params: dict, context: ToolContext) -> dict:
    """Deploy to a percentage of traffic."""
    pct = params.get("percentage", 10)
    service = params.get("service", "")

    logger.info("deploy_canary: %d%% for %s", pct, service)

    return {
        "status": "RUNNING",
        "traffic_routed_pct": pct,
        "service": service,
        "message": f"Canary {pct}% — metrics nominal",
    }


deploy_canary_tool = MCPTool(
    name="deploy_canary",
    description="Deploy to a percentage of traffic (canary). Passes through Secure Broker.",
    handler=deploy_canary_handler,
    input_schema={
        "type": "object",
        "properties": {
            "percentage": {"type": "integer"},
            "service": {"type": "string"},
        },
        "required": ["percentage", "service"],
    },
)


# ═══════════════════════════════════════════════════════════════
# monitor
# ═══════════════════════════════════════════════════════════════

async def monitor_handler(params: dict, context: ToolContext) -> dict:
    """Monitor metrics during canary."""
    duration = params.get("duration_minutes", 5)
    service = params.get("service", "")

    logger.info("monitor: %s for %d min", service, duration)

    return {
        "error_rate_pct": 0.01,
        "latency_p95_ms": 120,
        "throughput_rps": 850,
        "status": "HEALTHY",
        "duration_minutes": duration,
        "service": service,
    }


monitor_tool = MCPTool(
    name="monitor",
    description="Monitor error rate, latency, and throughput during canary deployment.",
    handler=monitor_handler,
    input_schema={
        "type": "object",
        "properties": {
            "duration_minutes": {"type": "integer"},
            "service": {"type": "string"},
        },
        "required": ["duration_minutes", "service"],
    },
)


# ═══════════════════════════════════════════════════════════════
# deploy_full
# ═══════════════════════════════════════════════════════════════

async def deploy_full_handler(params: dict, context: ToolContext) -> dict:
    """Deploy to 100% traffic."""
    service = params.get("service", "")

    logger.info("deploy_full: %s", service)

    return {
        "status": "DEPLOYED",
        "traffic_routed_pct": 100,
        "service": service,
        "duration_sec": 30,
    }


deploy_full_tool = MCPTool(
    name="deploy_full",
    description="Deploy to 100% traffic. Called after successful canary + monitoring.",
    handler=deploy_full_handler,
    input_schema={
        "type": "object",
        "properties": {
            "service": {"type": "string"},
        },
        "required": ["service"],
    },
)


# ═══════════════════════════════════════════════════════════════
# rollback
# ═══════════════════════════════════════════════════════════════

async def rollback_handler(params: dict, context: ToolContext) -> dict:
    """Emergency rollback."""
    service = params.get("service", "")
    version = params.get("rollback_version", "previous")

    logger.warning("rollback: %s → %s", service, version)

    return {
        "status": "ROLLED_BACK",
        "traffic_restored_pct": 100,
        "service": service,
        "version": version,
        "duration_sec": 10,
    }


rollback_tool = MCPTool(
    name="rollback",
    description="Emergency rollback. Called when monitoring detects degraded metrics.",
    handler=rollback_handler,
    input_schema={
        "type": "object",
        "properties": {
            "service": {"type": "string"},
            "rollback_version": {"type": "string"},
        },
        "required": ["service"],
    },
)