"""
ChangeGuard AI Adaptive CI/CD MCP Server
================================
Executes what the Agent orders. Reports results. Never decides.

Tools:
  run_tests       — Execute test suite
  deploy_canary   — Canary deployment
  monitor         — Monitor metrics
  deploy_full     — Full deployment
  rollback        — Emergency rollback

Modes:
  simulated — Mock results with realistic timing (hackathon)
  live      — Real GitHub Actions + Cloud Run + Cloud Monitoring

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
logger = logging.getLogger("changeguard-cicd")

from mcp.server.fastmcp import FastMCP

MODE = os.getenv("CICD_MODE", "simulated")

from tools.run_tests import run_tests_handler
from tools.deploy_canary import deploy_canary_handler
from tools.monitor import monitor_handler
from tools.deploy_full import deploy_full_handler
from tools.rollback import rollback_handler
from tools.github_pr import comment_pr_handler, merge_pr_handler

# ═══════════════════════════════════════════════════════════════
# MCP SERVER
# ═══════════════════════════════════════════════════════════════

port = int(os.getenv("PORT", "8082"))
app = FastMCP(
    "adaptive-cicd-server",
    host="0.0.0.0",
    port=port,
    log_level="INFO",
    stateless_http=True,
)


@app.tool()
async def run_tests(test_plan: list, pr_id: str) -> dict:
    """
    Execute a test suite.
    
    Args:
        test_plan: List of test names to execute.
        pr_id: Pull request ID.
    
    Returns:
        Test result with total, passed, failed, duration.
    """
    return await run_tests_handler(test_plan, pr_id, MODE)


@app.tool()
async def deploy_canary(percentage: int, service: str, pr_id: str = "unknown") -> dict:
    """
    Deploy a canary revision to a percentage of traffic.
    
    Args:
        percentage: Traffic percentage (1-100).
        service: Service name to deploy.
    
    Returns:
        Deploy result with status and traffic info.
    """
    return await deploy_canary_handler(percentage, service, MODE, pr_id)


@app.tool()
async def monitor(duration_minutes: int, service: str,
                  simulated_error_rate: float = None, pr_id: str = "unknown") -> dict:
    """
    Monitor canary metrics for a specified duration.
    
    Args:
        duration_minutes: How long to monitor.
        service: Service to monitor.
        simulated_error_rate: Override error rate for demo scenarios.
    
    Returns:
        Monitor result with error rate, latency, throughput, status.
    """
    return await monitor_handler(duration_minutes, service, MODE, simulated_error_rate, pr_id)


@app.tool()
async def deploy_full(service: str, pr_id: str = "unknown") -> dict:
    """
    Promote canary to 100% traffic.
    
    Args:
        service: Service to fully deploy.
    
    Returns:
        Deploy result.
    """
    return await deploy_full_handler(service, MODE, pr_id)


@app.tool()
async def comment_pr(pr_url: str, body: str) -> dict:
    """Post an approved ChangeGuard assessment as a GitHub pull request comment."""
    return await comment_pr_handler(pr_url, body)


@app.tool()
async def merge_pr(pr_url: str, merge_method: str = "squash") -> dict:
    """Merge an approved GitHub pull request using the requested merge method."""
    return await merge_pr_handler(pr_url, merge_method)


@app.tool()
async def rollback(service: str, rollback_version: str = "previous", pr_id: str = "unknown") -> dict:
    """
    Emergency rollback to previous stable revision.
    
    Args:
        service: Service to rollback.
        rollback_version: Version to rollback to.
    
    Returns:
        Rollback result.
    """
    return await rollback_handler(service, rollback_version, MODE, pr_id)


logger.info("Tools registered: run_tests, deploy_canary, monitor, deploy_full, rollback, comment_pr, merge_pr")
logger.info("Mode: %s", MODE)

# ═══════════════════════════════════════════════════════════════
# START
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Adaptive CI/CD Server starting on port %d (streamable-http)", port)
    logger.info("=" * 60)
    app.run(transport="streamable-http")