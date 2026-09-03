"""Deterministic pull-request risk analysis used by the ChangeGuard workflow."""

from typing import Any

from google.adk.tools import ToolContext

try:
    from ..risk_engine.rules import SERVICE_CONSUMERS
    from ..risk_engine.scoring import calculate_risk_score
    from ..risk_engine.services import has_schema_change, identify_affected_services, is_new_endpoint
    from ..risk_engine.test_plan import generate_suggested_tests, generate_test_plan
except ImportError:  # pragma: no cover
    from risk_engine.rules import SERVICE_CONSUMERS
    from risk_engine.scoring import calculate_risk_score
    from risk_engine.services import has_schema_change, identify_affected_services, is_new_endpoint
    from risk_engine.test_plan import generate_suggested_tests, generate_test_plan


async def analyze_pr_handler(params: dict[str, Any], context: ToolContext | None = None) -> dict:
    """Assess risk from the changed files and description of an already validated PR."""
    pr_id = params["pr_id"]
    pr_title = params["pr_title"]
    files_changed = params.get("files_changed", [])
    diff_summary = params.get("diff_summary", "")
    affected_services = identify_affected_services(files_changed)
    coverage_gap_detected = is_new_endpoint(diff_summary, files_changed)
    schema_changed = has_schema_change(files_changed)
    risk = calculate_risk_score(
        files_changed=files_changed,
        diff_summary=diff_summary,
        contract_has_breaking=schema_changed and "breaking" in diff_summary.lower(),
        affected_services=affected_services,
        test_coverage_zero=coverage_gap_detected,
    )

    if coverage_gap_detected:
        test_plan = []
        suggested_new_tests = generate_suggested_tests(diff_summary, affected_services)
        consumer_count = 0
    else:
        test_plan = generate_test_plan(affected_services)
        suggested_new_tests = []
        consumer_count = sum(SERVICE_CONSUMERS.get(service, 0) for service in affected_services)

    reasoning_parts = [
        f"PR #{pr_id}: '{pr_title}'.",
        f"Affected services: {', '.join(affected_services)} ({consumer_count} consumers).",
        *risk["reasons"],
        f"Decision: {risk['decision']}.",
        f"Strategy: {risk['strategy']}.",
    ]
    if coverage_gap_detected:
        reasoning_parts.append(f"ZERO test coverage. {len(suggested_new_tests)} tests suggested.")

    return {
        "pr_id": pr_id,
        "pr_title": pr_title,
        "risk_score": risk["score"],
        "decision": risk["decision"],
        "affected_services": affected_services,
        "affected_consumers_count": consumer_count,
        "test_plan": test_plan,
        "suggested_new_tests": suggested_new_tests,
        "coverage_gap_detected": coverage_gap_detected,
        "deployment_strategy": risk["strategy"],
        "reasoning": " ".join(reasoning_parts),
        "escalation_log": risk["reasons"],
        "files_analyzed": len(files_changed),
    }
