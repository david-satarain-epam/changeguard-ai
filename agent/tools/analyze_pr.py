"""
Main tool: analyze_pr
Receives PR payload → returns risk assessment.
"""

import logging
from google.adk.tools import MCPTool, ToolContext

logger = logging.getLogger("changeguard-agent.tools")

from risk_engine.services import (
    identify_affected_services,
    has_schema_change,
    is_new_endpoint,
)
from risk_engine.scoring import calculate_risk_score
from risk_engine.rules import SERVICE_CONSUMERS
from risk_engine.test_plan import generate_test_plan, generate_suggested_tests


async def analyze_pr_handler(params: dict, context: ToolContext) -> dict:
    """Analyze a PR and return complete risk assessment."""
    pr_id = params["pr_id"]
    title = params["title"]
    files_changed = params.get("files_changed", [])
    diff_summary = params.get("diff_summary", "")

    logger.info("━" * 60)
    logger.info("PR #%s: %s", pr_id, title)
    logger.info("Files: %s", files_changed)

    # Step 1: Identify affected services
    affected_services = identify_affected_services(files_changed)
    logger.info("Services: %s", affected_services)

    # Step 2: Detect new endpoints
    coverage_zero = is_new_endpoint(diff_summary, files_changed)
    if coverage_zero:
        logger.warning("New endpoint detected — zero coverage")

    # Step 3: Detect schema changes
    schema_changed = has_schema_change(files_changed)

    # Step 4: Calculate risk
    risk = calculate_risk_score(
        files_changed=files_changed,
        diff_summary=diff_summary,
        contract_has_breaking=schema_changed and "breaking" in diff_summary.lower(),
        affected_services=affected_services,
        test_coverage_zero=coverage_zero,
    )
    logger.info("Risk: %s → %s (%s)", risk["score"], risk["decision"], risk["strategy"])

    # Step 5: Generate test plan
    if coverage_zero:
        test_plan = []
        suggested_tests = generate_suggested_tests(diff_summary, affected_services)
        consumer_count = 0
    else:
        test_plan = generate_test_plan(affected_services)
        suggested_tests = []
        consumer_count = sum(
            SERVICE_CONSUMERS.get(svc, 0) for svc in affected_services
        )

    # Step 6: Build reasoning
    parts = [
        f"PR #{pr_id}: '{title}'.",
        f"Affected services: {', '.join(affected_services)} ({consumer_count} consumers).",
        *risk["reasons"],
        f"Decision: {risk['decision']}.",
        f"Strategy: {risk['strategy']}.",
    ]
    if coverage_zero:
        parts.append(
            f"ZERO test coverage. {len(suggested_tests)} tests suggested."
        )

    return {
        "pr_id": pr_id,
        "title": title,
        "risk_score": risk["score"],
        "decision": risk["decision"],
        "affected_services": affected_services,
        "affected_consumers_count": consumer_count,
        "test_plan": test_plan,
        "suggested_new_tests": suggested_tests,
        "coverage_gap_detected": coverage_zero,
        "deployment_strategy": risk["strategy"],
        "reasoning": " ".join(parts),
        "escalation_log": risk["reasons"],
        "files_analyzed": len(files_changed),
    }


analyze_pr_tool = MCPTool(
    name="analyze_pr",
    description=(
        "Analyze a pull request and return risk assessment with deployment "
        "recommendation. Detects coverage gaps for new endpoints."
    ),
    handler=analyze_pr_handler,
    input_schema={
        "type": "object",
        "properties": {
            "pr_id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "files_changed": {"type": "array", "items": {"type": "string"}},
            "diff_summary": {"type": "string"},
            "repo": {"type": "string"},
        },
        "required": ["pr_id", "title", "files_changed", "diff_summary"],
    },
)