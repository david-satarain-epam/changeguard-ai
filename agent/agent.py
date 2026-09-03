"""ChangeGuard AI — PR Risk Assessment Workflow."""

import os
import re
from pathlib import Path
from typing import Any
import dotenv
from pydantic import BaseModel
from google.adk import Agent
from google.adk import Context
from google.adk import Workflow
from google.adk.apps import App, ResumabilityConfig
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import node

try:
    from .tools import simulate_pipeline
    from .tools.analyze_pr import analyze_pr_handler
    from .tools.github_api import fetch_github_pr
    from .tools.executions_tools import broker_toolset, call_broker
    from .tools.report_renderer import html_artifact, render_report_html, text_summary
except ImportError:  # pragma: no cover
    from tools.github_api import fetch_github_pr
    from tools.analyze_pr import analyze_pr_handler
    from tools.pipeline_simulator import simulate_pipeline
    from tools.executions_tools import broker_toolset, call_broker
    from tools.report_renderer import html_artifact, render_report_html, text_summary

dotenv.load_dotenv(Path(__file__).with_name(".env"))

MODEL = os.environ["MODEL"]


class ApprovalDecision(BaseModel):
    """Structured interpretation of the user's deployment decision."""

    decision: str


def _map_workflow_final_status(payload: dict) -> str:
    """Convert GitHub Actions workflow status into a ChangeGuard final status."""
    if not isinstance(payload, dict):
        return "UNKNOWN"

    status = (payload.get("workflow_status") or payload.get("status") or "").lower()
    conclusion = (payload.get("conclusion") or "").lower()

    if conclusion == "success":
        return "SUCCESS"
    if conclusion in {"failure", "timed_out"}:
        return "FAILED"
    if conclusion == "cancelled":
        return "CANCELLED"
    if status in {"in_progress", "queued", "requested", "waiting", "pending", "running"}:
        return "IN_PROGRESS"
    if status == "completed" and not conclusion:
        return "FAILED"
    if status == "completed":
        return "SUCCESS"
    return "UNKNOWN"


# ─── Workflow Nodes ───────────────────────────────────────────────

@node(name="fetch_prs_node")
def fetch_prs_node(ctx: Context, node_input: Any) -> Event:
    """Fetch a PR, or accept a fallback approval reply from the normal chat box."""
    if hasattr(node_input, "parts"):
        user_text = "".join(p.text for p in node_input.parts if p.text).strip()
    elif isinstance(node_input, dict) and "parts" in node_input:
        user_text = "".join(p.get("text", "") for p in node_input["parts"]).strip()
    else:
        user_text = str(node_input).strip()

    if not re.search(r"https?://github\.com/[^/\s]+/[^/\s]+/pull/\d+", user_text):
        if ctx.state.get("approval_status") == "pending" and ctx.state.get("assessments_data"):
            return Event(
                output={"approval_response": user_text},
                route="approval_response",
                state={"approval_response": user_text},
            )
        raise ValueError(
            "A pull request URL is required: https://github.com/owner/repo/pull/123"
        )
    pr = fetch_github_pr(user_text)
    result = {"repo_url": user_text, "repo_owner": pr["repo_owner"], "repo_name": pr["repo_name"], "prs": [pr]}
    return Event(state={"prs_data": result}, output=result, route="new_pr")


async def execute_strategy(assessment: dict) -> dict:
    """Run the selected CI/CD strategy through broker authorization."""
    strategy = assessment.get("deployment_strategy", "NONE")
    service = (assessment.get("affected_services") or ["unknown"])[0]
    pr_id = assessment.get("pr_id", "unknown")
    stages = []

    if strategy == "NONE":
        return {"stages": [], "final_status": "POSTPONED", "total_duration_seconds": 0}

    tests = await call_broker(
        "run_tests",
        {"test_plan": assessment.get("test_plan", []), "pr_id": pr_id},
        f"pr-{pr_id}",
    )
    test_result = tests.get("forward_result", tests)
    stages.append({"name": "run_tests", **test_result})
    if not tests.get("authorized") or test_result.get("error"):
        return {"stages": stages, "final_status": "FAILED", "total_duration_seconds": 0}

    workflow_outcome = _map_workflow_final_status(test_result)
    if workflow_outcome in {"FAILED", "CANCELLED"}:
        return {"stages": stages, "final_status": workflow_outcome, "total_duration_seconds": 0}
    if workflow_outcome == "IN_PROGRESS":
        return {"stages": stages, "final_status": "IN_PROGRESS", "total_duration_seconds": 0}

    if strategy == "CANARY":
        canary = await call_broker("deploy_canary", {"percentage": 10, "service": service, "pr_id": pr_id}, f"pr-{pr_id}")
        canary_result = canary.get("forward_result", canary)
        stages.append({"name": "deploy_canary", **canary_result})
        if not canary.get("authorized") or canary_result.get("error"):
            return {"stages": stages, "final_status": "FAILED", "total_duration_seconds": 0}
        canary_outcome = _map_workflow_final_status(canary_result)
        if canary_outcome in {"FAILED", "CANCELLED"}:
            return {"stages": stages, "final_status": canary_outcome, "total_duration_seconds": 0}
        if canary_outcome == "IN_PROGRESS":
            return {"stages": stages, "final_status": "IN_PROGRESS", "total_duration_seconds": 0}
        monitor = await call_broker("monitor", {"duration_minutes": 5, "service": service, "pr_id": pr_id}, f"pr-{pr_id}")
        monitor_result = monitor.get("forward_result", monitor)
        stages.append({"name": "monitor", **monitor_result})
        if not monitor.get("authorized") or monitor_result.get("error"):
            return {"stages": stages, "final_status": "FAILED", "total_duration_seconds": 0}
        monitor_outcome = _map_workflow_final_status(monitor_result)
        if monitor_outcome in {"FAILED", "CANCELLED"}:
            return {"stages": stages, "final_status": monitor_outcome, "total_duration_seconds": 0}
        if monitor_outcome == "IN_PROGRESS":
            return {"stages": stages, "final_status": "IN_PROGRESS", "total_duration_seconds": 0}

    deploy = await call_broker("deploy_full", {"service": service, "pr_id": pr_id}, f"pr-{pr_id}")
    deploy_result = deploy.get("forward_result", deploy)
    stages.append({"name": "deploy_full", **deploy_result})
    if not deploy.get("authorized") or deploy_result.get("error"):
        return {"stages": stages, "final_status": "FAILED", "total_duration_seconds": 0}

    failed = _map_workflow_final_status(deploy_result) in {"FAILED", "CANCELLED"}
    in_progress = _map_workflow_final_status(deploy_result) == "IN_PROGRESS"
    duration = sum(stage.get("duration_seconds", 0) for stage in stages)
    final_status = "FAILED" if failed else "IN_PROGRESS" if in_progress else "SUCCESS"
    return {"stages": stages, "final_status": final_status, "total_duration_seconds": duration}

def _approval_summary(assessment: dict) -> str:
    """Build the human review shown before ChangeGuard can modify a PR."""
    services = ", ".join(assessment.get("affected_services", [])) or "None identified"
    reasons = assessment.get("escalation_log", [])
    reason_list = "\n".join(f"  - {reason}" for reason in reasons) or "  - No additional risk factors detected."
    test_plan = assessment.get("test_plan", [])
    tests = ", ".join(test_plan) if test_plan else "No automated tests were selected."
    strategy = assessment.get("deployment_strategy", "NONE")
    strategy_actions = {
        "DIRECT": "run tests, then deploy to 100% traffic",
        "GATED": "run tests, then deploy after this approval",
        "CANARY": "run tests, deploy a 10% canary, monitor it, then deploy to 100% traffic",
        "NONE": "do not deploy",
    }.get(strategy, "execute the proposed CI/CD strategy")
    reasoning = assessment.get("reasoning", "No reasoning available.")

    return (
        f"PR #{assessment.get('pr_id', 'unknown')}: {assessment.get('pr_title', 'Untitled PR')}\n"
        f"Risk: {assessment.get('risk_score', 'UNKNOWN')} | Decision: {assessment.get('decision', 'UNKNOWN')} | "
        f"Strategy: {strategy}\n"
        f"Affected services: {services}\n"
        f"Affected consumers: {assessment.get('affected_consumers_count', 0)}\n"
        f"Files analyzed: {assessment.get('files_analyzed', 0)}\n"
        f"Coverage gap detected: {'Yes' if assessment.get('coverage_gap_detected') else 'No'}\n"
        f"Recommended tests: {tests}\n"
        f"Risk factors:\n{reason_list}\n\n"
        "PR comment preview:\n"
        "## ChangeGuard AI Assessment\n\n"
        f"**Risk:** {assessment.get('risk_score', 'UNKNOWN')}\n\n"
        f"**Recommended strategy:** {strategy}\n\n"
        f"**Reasoning:** {reasoning}\n\n"
        f"After approval, ChangeGuard will post this comment, merge the PR, and {strategy_actions}."
    )


@node(name="request_approval_node", rerun_on_resume=True)
async def request_approval_node(ctx: Context, node_input: Any):
    """Pause after analysis and resume only with an explicit user decision."""
    interrupt_id = ctx.state["approval_interrupt_id"]
    if interrupt_id not in ctx.resume_inputs:
        assessments = node_input.get("assessments", []) if isinstance(node_input, dict) else []
        summaries = "\n\n".join(_approval_summary(item) for item in assessments)
        approval_message = (
            "ChangeGuard analysis is complete. Please review the proposed actions:\n\n"
            + summaries + "\n\n"
            "Reply in this chat to authorize ChangeGuard to post the shown comment, merge the PR, "
            "and execute the stated CI/CD strategy. You can also reject the plan."
        )
        yield Event(message=approval_message)
        yield RequestInput(
            interruptId=interrupt_id,
            message="Waiting for your approval or rejection.",
            responseSchema=str,
        )
        return

    response = ctx.resume_inputs[interrupt_id]
    yield Event(output={"approval_response": response}, state={"approval_response": response})


approval_interpreter = Agent(
    name="approval_interpreter",
    model=MODEL,
    output_schema=ApprovalDecision,
    instruction="""
Interpret the user's answer to a request to comment on, merge, and deploy a pull request.
Return JSON only with decision set to exactly one of: approved, rejected, clarification.
Treat natural language, Spanish or English, short replies, and obvious typos according to the user's intent.
Use approved only when the user clearly authorizes all three actions: post the comment, merge, and execute the strategy.
Use rejected when the user declines execution. Use clarification if the intent is genuinely ambiguous.
User answer: {approval_response}
""",
)


@node(name="execute_approved_strategy_node")
async def execute_approved_strategy_node(ctx: Context, node_input: Any) -> Event:
    """Post the assessment, merge the approved PR, then reuse the existing CI/CD executor."""
    decision = str(node_input.get("decision", "clarification")).lower() if isinstance(node_input, dict) else "clarification"
    assessment_data = ctx.state.get("assessments_data", {})
    assessments = list(assessment_data.get("assessments", []))

    if decision != "approved":
        status = "ANALYSIS_ONLY" if decision == "rejected" else "PENDING_APPROVAL"
        message = "User declined CI/CD execution." if decision == "rejected" else "User response needs clarification before any PR action."
        for assessment in assessments:
            assessment["pipeline_execution"] = {
                "stages": [],
                "final_status": status,
                "total_duration_seconds": 0,
                "message": message,
            }
        result = {**assessment_data, "assessments": assessments}
        return Event(state={"assessments_data": result, "approval_status": decision}, output=result)

    results = []
    live_mode = os.getenv("LAYER_MODE", "mock").lower() == "live"
    for assessment in assessments:
        if not live_mode:
            assessment["pipeline_execution"] = simulate_pipeline(assessment)
            results.append(assessment)
            continue

        comment_body = (
            "## ChangeGuard AI Assessment\n\n"
            f"**Risk:** {assessment['risk_score']}\n\n"
            f"**Recommended strategy:** {assessment['deployment_strategy']}\n\n"
            f"**Reasoning:** {assessment['reasoning']}"
        )
        comment_call = await call_broker("comment_pr", {"pr_url": assessment["pr_url"], "body": comment_body}, f"pr-{assessment['pr_id']}")
        comment = comment_call.get("forward_result", comment_call)
        governance_stages = [{"name": "pr_comment", "status": comment.get("status", "FAILED"), "details": comment.get("details") or comment.get("error", "Comment result")}]
        if not comment_call.get("authorized") or comment.get("status") != "SUCCESS":
            assessment["pipeline_execution"] = {"stages": governance_stages, "final_status": "FAILED", "total_duration_seconds": 0}
            results.append(assessment)
            continue

        merge_call = await call_broker("merge_pr", {"pr_url": assessment["pr_url"], "merge_method": os.getenv("GITHUB_MERGE_METHOD", "squash")}, f"pr-{assessment['pr_id']}")
        merge = merge_call.get("forward_result", merge_call)
        governance_stages.append({"name": "pr_merge", "status": merge.get("status", "FAILED"), "details": merge.get("details") or merge.get("error", "Merge result")})
        if not merge_call.get("authorized") or merge.get("status") != "SUCCESS":
            assessment["pipeline_execution"] = {"stages": governance_stages, "final_status": "FAILED", "total_duration_seconds": 0}
            results.append(assessment)
            continue

        pipeline = await execute_strategy(assessment)
        pipeline["stages"] = governance_stages + pipeline.get("stages", [])
        pipeline["total_duration_seconds"] = sum(stage.get("duration_seconds", 0) for stage in pipeline["stages"])
        assessment["pipeline_execution"] = pipeline
        results.append(assessment)

    result = {**assessment_data, "assessments": results}
    return Event(state={"assessments_data": result, "approval_status": "approved"}, output=result)

@node(name="assess_prs_node")
async def assess_prs_node(ctx: Context, node_input: Any) -> Event:
    """Score one PR and prepare its strategy for explicit user approval."""
    prs = node_input.get("prs", [])

    assessments = []
    for pr in prs:
        assessment = await analyze_pr_handler(
            {
                "pr_id": pr["pr_id"],
                "pr_title": pr["pr_title"],
                "files_changed": pr.get("changed_files", []),
                "diff_summary": pr.get("description", ""),
            },
            None,
        )
        assessment["pr_url"] = pr.get("pr_url", "")
        assessment["pipeline_execution"] = {
            "stages": [],
            "final_status": "PENDING_APPROVAL",
            "total_duration_seconds": 0,
            "requires_approval": True,
            "approval_status": "pending",
            "message": "Waiting for user approval before posting a PR comment, merging, or executing CI/CD.",
        }
        assessments.append(assessment)

    result = {
        "repo_url":    node_input.get("repo_url", ""),
        "repo_name":   node_input.get("repo_name", ""),
        "assessments": assessments,
    }
    return Event(
        state={
            "assessments_data": result,
            "approval_interrupt_id": f"deployment_approval_{ctx.run_id}",
            "approval_status": "pending",
        },
        output=result,
    )


# ─── Phase 2: Synthesis Agent ────────────────────────────────────
# Receives the fully-scored assessments and produces the final JSON report array.
# Uses ADK state injection: {assessments_data} is replaced at runtime with the
# serialized output of assess_prs_node.

synthesis_agent = Agent(
    name="synthesis_agent",
    model=MODEL,
    instruction="""
You are the final reporting agent for ChangeGuard AI.

You receive a structured object containing risk assessments for all open PRs in a repository.
Assessment data:
{assessments_data}

Return a JSON array — one object per PR — with this exact top-level structure for each item:

  report_html         : A placeholder HTML string for the PR card. Use this template exactly:
                        "<div style='font-family:-apple-system,sans-serif;padding:16px;border-radius:8px;border:1px solid #e0e0e0;margin:8px 0'><h3>[PR_TITLE] <span style='font-size:12px;padding:2px 8px;border-radius:12px;background:[RISK_COLOR];color:white'>[RISK_SCORE]</span></h3><p><strong>Decision:</strong> [DECISION] &nbsp; <strong>Strategy:</strong> [STRATEGY]</p><p style='color:#555'>[ONE_LINE_SUMMARY]</p></div>"
                        RISK_COLOR mapping: LOW=#28a745  MEDIUM=#ffc107  HIGH=#fd7e14  CRITICAL=#dc3545

  report_metadata     : Object with keys:
                          workflow_id            (string, format: "wf-20260830-[pr_id]")
                          pr_id                  (string, from assessment)
                          pr_title               (string, from assessment)
                          generated_at           (string, current UTC ISO 8601 timestamp generated at runtime; never use a fixed demo date)
                          total_duration_seconds (number, from pipeline_execution.total_duration_seconds)
                          status                 (string, from pipeline_execution.final_status)

  impact_analysis     : Object with keys:
                          risk_score               (string, copy from assessment — do NOT change)
                          decision                 (string, copy from assessment — do NOT change)
                          strategy                 (string, copy deployment_strategy — do NOT change)
                          affected_services        (array, copy from assessment)
                          affected_consumers_count (number, copy from assessment)
                          reasoning                (string, write 2-3 specific sentences explaining
                                                   why this PR carries this risk level, what makes it
                                                   safe or dangerous, and what the deployment approach achieves)
                          escalation_log           (array, copy from assessment)
                          coverage_gap_detected    (boolean, copy from assessment)
                          context_sources          (object, copy from assessment)

  pipeline_execution  : Copy the full pipeline_execution object directly from the assessment.

STRICT RULES:
- Return ONLY a valid JSON array. No markdown fences, no prose, no extra keys.
- Never modify risk_score, decision, strategy, or any numeric field from the input.
- The reasoning must be specific to this PR — reference its actual title, services, and risk factors.
- For report_html, substitute all placeholders ([PR_TITLE], [RISK_COLOR], etc.) with real values.
- Copy pipeline_execution exactly as supplied. This workflow has already performed any approved actions.
- Do not call any tool and do not propose, comment, merge, or deploy anything.
""",
)


@node(name="attach_final_report_node")
async def attach_final_report_node(ctx: Context, node_input: Any) -> Event:
    """Attach the synthesis output as a standalone HTML dashboard artifact."""
    report_html = render_report_html(node_input)
    await ctx.save_artifact(
        "changeguard-report.html",
        html_artifact(report_html),
        custom_metadata={"mime_type": "text/html", "source": "app_final.html"},
    )
    return Event(
        state={"final_report_html": "changeguard-report.html"},
        output=text_summary(node_input),
    )


# ─── Workflow ────────────────────────────────────────────────────

pr_workflow = Workflow(
    name="pr_risk_workflow",
    edges=[
        ("START", fetch_prs_node),
        (fetch_prs_node, {
            "new_pr": assess_prs_node,
            "approval_response": approval_interpreter,
        }),
        (assess_prs_node, request_approval_node),
        (request_approval_node, approval_interpreter),
        (approval_interpreter, execute_approved_strategy_node),
        (execute_approved_strategy_node, synthesis_agent),
        (synthesis_agent, attach_final_report_node),
    ],
)


# ─── App ─────────────────────────────────────────────────────────

main_app = App(
    name="support_agent",
    root_agent=pr_workflow,
    resumability_config=ResumabilityConfig(is_resumable=True),
)

# ADK web loads `app` before `root_agent`; exporting this preserves the
# configured resumability instead of letting the CLI wrap the workflow again.
app = main_app

# root_agent is required by `adk web` to discover and run this agent.
# When running via the web UI the user types the repo URL directly in
# the chat box; fetch_prs_node picks it up from the first message.
root_agent = pr_workflow
