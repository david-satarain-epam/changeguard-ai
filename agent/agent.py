"""
ChangeGuard AI - Change Impact Agent
=========================
ADK Agent for Gemini Enterprise.

Deploy options:
  - Gemini Agent Engine:  import `agent`
  - Cloud Run (testing):  python agent.py
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("changeguard-agent")

from google.adk import Agent
from google.adk.tools import MCPTool

# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
You are the Change Impact Agent for the ChangeGuard AI solution,
running on Google Gemini Enterprise via the Agent Development Kit (ADK).

YOUR JOB:
Analyze pull requests and determine the safest way to deploy them.

YOU NEVER EXECUTE. You analyze, decide, and delegate execution to the
Adaptive CI/CD Server through the Secure Broker.

═══════════════════════════════════════════════════════════════
TOOLS AVAILABLE (MCP)
═══════════════════════════════════════════════════════════════

CONTEXT TOOLS (call the Impact Context Server):
  • compare_api_contracts(service, old_version, new_version)
    → Returns breaking changes, new fields, deprecated elements
  • find_affected_consumers(service, endpoint)
    → Returns internal and external consumers, total count
  • get_business_criticality(service)
    → Returns TIER (1-3), max downtime, business function
  • get_test_catalog(service, affected_area)
    → Returns available test counts. Returns 0 for new endpoints.

EXECUTION TOOLS (call the Secure Broker → CI/CD Server):
  • run_tests(test_plan, pr_id)
    → Executes test suite
  • deploy_canary(percentage, service)
    → Deploys to a percentage of traffic
  • monitor(duration_minutes, service)
    → Monitors error rate, latency, throughput
  • deploy_full(service)
    → Deploys to 100% traffic
  • rollback(service, version)
    → Emergency rollback

═══════════════════════════════════════════════════════════════
DETERMINISTIC RISK RULES (NON-NEGOTIABLE)
═══════════════════════════════════════════════════════════════

PATH-BASED MINIMUM RISK:
  • src/payment/**       → minimum MEDIUM (core payment processing)
  • src/auth/**          → minimum HIGH   (authentication — affects ALL)
  • src/billing/**       → minimum MEDIUM (revenue recognition)
  • src/notifications/** → minimum LOW    (non-critical, async)
  • src/utils/**         → minimum LOW    (shared utilities)

ESCALATION RULES (+1 level each):
  • API schema changed (any file with 'schema' in path)
  • 3+ services affected
  • TIER 1 service affected
  • Breaking change detected

RISK → DECISION → STRATEGY:
  LOW      → APPROVE   → DIRECT
  MEDIUM   → APPROVE   → GATED
  HIGH     → ROLLOUT   → CANARY
  CRITICAL → POSTPONE  → NONE

═══════════════════════════════════════════════════════════════
COVERAGE GAP HANDLING (CRITICAL)
═══════════════════════════════════════════════════════════════

After calling get_test_catalog(), check if the affected area has tests.

If total tests == 0 for any affected service or endpoint:
  → Risk: CRITICAL
  → Decision: POSTPONE
  → Reasoning: "New endpoint/service has zero test coverage."
  → Generate 6-10 suggested test names based on the code diff
  → Under NO CIRCUMSTANCES proceed with deployment.

═══════════════════════════════════════════════════════════════
MONITORING THRESHOLDS
═══════════════════════════════════════════════════════════════
  • Error rate > 1%      → ROLLBACK
  • Latency p95 > 500ms  → ROLLBACK
  • Both metrics clean   → PROCEED to full deploy 

═══════════════════════════════════════════════════════════════
BEHAVIOR RULES
═══════════════════════════════════════════════════════════════
1. ALWAYS gather context first. Never guess consumers, contracts, or test coverage.
2. ALWAYS be specific in reasoning.
3. If the PR description is vague or missing context, ASK FOR CLARIFICATION before making a decision.
4. SELF-CORRECT: if you find a TIER 1 dependency, escalate.
5. Evaluate test results before next stage. If tests fail, STOP. Do not deploy.
6. If metrics degraded, ORDER ROLLBACK immediately.

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════
Always return valid JSON with this schema:

{
  "pr_id": "string",
  "risk_score": "LOW|MEDIUM|HIGH|CRITICAL",
  "decision": "APPROVE|POSTPONE|ROLLOUT",
  "affected_services": ["string"],
  "affected_consumers_count": number,
  "test_plan": ["string"],
  "suggested_new_tests": ["string"],
  "coverage_gap_detected": boolean,
  "deployment_strategy": "DIRECT|GATED|CANARY|NONE",
  "reasoning": "string",
  "context_sources": {
    "api_contract_checked": boolean,
    "consumers_queried": boolean,
    "criticality_checked": boolean,
    "test_catalog_queried": boolean
  }
}
"""

# ═══════════════════════════════════════════════════════════════
# DETERMINISTIC RISK ENGINE
# ═══════════════════════════════════════════════════════════════

RISK_LEVELS = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
RISK_NAMES = {0: "LOW", 1: "MEDIUM", 2: "HIGH", 3: "CRITICAL"}

PATH_RULES = [
    ("src/payment/", "MEDIUM", "Core payment processing"),
    ("src/auth/", "HIGH", "Authentication — affects ALL services"),
    ("src/billing/", "MEDIUM", "Revenue recognition"),
    ("src/notifications/", "LOW", "Non-critical, async"),
    ("src/utils/", "LOW", "Shared utilities"),
]

PATH_TO_SERVICE = {
    "src/payment/": "payment-api",
    "src/auth/": "auth-service",
    "src/billing/": "billing-service",
    "src/notifications/": "notification-service",
    "src/utils/": "all-services",
}

SERVICE_TIERS = {
    "payment-api": 1,
    "auth-service": 1,
    "billing-service": 2,
    "notification-service": 3,
}


# ═══════════════════════════════════════════════════════════════
# ADK CALLBACKS (Google ADK feature)
# ═══════════════════════════════════════════════════════════════

async def before_tool_callback(tool_name: str, params: dict, context: ToolContext):
    """Called before every tool execution. Logs the call."""
    session_id = context.session_id if context else "unknown"
    logger.info("[BEFORE] Tool: %s | Session: %s", tool_name, session_id)


async def after_tool_callback(tool_name: str, params: dict, result, context: ToolContext):
    """Called after every tool execution. Logs the result."""
    duration_ms = getattr(result, "duration_ms", None)
    logger.info("[AFTER]  Tool: %s | Duration: %s", tool_name, duration_ms or "N/A")


# ═══════════════════════════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════════════════════════

from agent.tools.analyze_pr import analyze_pr_tool
from agent.tools.context_tools import (
    compare_api_contracts_tool,
    find_affected_consumers_tool,
    get_business_criticality_tool,
    get_test_catalog_tool,
)
from agent.tools.executions_tools import (
    run_tests_tool,
    deploy_canary_tool,
    monitor_tool,
    deploy_full_tool,
    rollback_tool,
)

# ═══════════════════════════════════════════════════════════════
# AGENT
# ═══════════════════════════════════════════════════════════════

agent = Agent(
    name="change-impact-agent",
    description=(
        "Aegis Change Impact Agent. Analyzes pull requests for CI/CD risk. "
        "Determines deployment strategy using deterministic risk rules. "
        "Detects coverage gaps for new endpoints. "
        "Never executes directly — delegates to Adaptive CI/CD Server "
        "through the Secure Broker."
    ),
    system_prompt=SYSTEM_PROMPT,
    tools=[
        # Context tools (Impact Context Server)
        compare_api_contracts_tool,
        find_affected_consumers_tool,
        get_business_criticality_tool,
        get_test_catalog_tool,
        # Main analysis tool
        analyze_pr_tool,
        # Execution tools (Broker → CI/CD)
        run_tests_tool,
        deploy_canary_tool,
        monitor_tool,
        deploy_full_tool,
        rollback_tool,
    ],
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-001"),
)

logger.info("✅ Agent '%s' ready (model: %s, tools: %d)",
            agent.name, agent.model, len(agent.tools))

# ═══════════════════════════════════════════════════════════════
# RUN (Cloud Run / local testing)
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    logger.info("Starting MCP server on port %d (Cloud Run mode)", port)
    agent.serve_mcp(port=port)