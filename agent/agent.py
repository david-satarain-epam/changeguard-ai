"""ChangeGuard AI — PR Risk Assessment Workflow."""

import os
from typing import Any
import dotenv
from google.adk import Agent
from google.adk import Context
from google.adk import Workflow
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.workflow import node

try:
    from .tools import fetch_github_prs, calculate_pr_risk, simulate_pipeline
except ImportError:  # pragma: no cover
    from tools.github_api import fetch_github_prs
    from tools.risk_analyzer import calculate_pr_risk
    from tools.pipeline_simulator import simulate_pipeline

dotenv.load_dotenv()

MODEL = os.environ.get("MODEL", "gemini-2.0-flash")


# ─── Phase 1: Input Agent ────────────────────────────────────────
# Standalone conversational agent that validates the repository URL.
# Runs as its own App before the main workflow starts.

input_agent = Agent(
    name="input_agent",
    model=MODEL,
    instruction="""
You are the first step of the ChangeGuard AI PR Risk Assessor.

Your ONLY job is to extract a valid GitHub repository URL from the user message.

- If the message contains a valid GitHub repository URL (https://github.com/owner/repo),
  return ONLY that URL — no extra text, no punctuation.
- If the message is empty, unclear, or does not contain a valid GitHub repository URL,
  respond with EXACTLY this and nothing else:
  Please provide your GitHub repository URL (e.g., https://github.com/owner/repo):

Do not greet the user. Do not add explanations.
""",
)


# ─── Phase 2: Workflow Nodes ─────────────────────────────────────

@node(name="fetch_prs_node")
def fetch_prs_node(ctx: Context, node_input: Any) -> Event:
    """Fetch the 10 most recent open PRs from the repository URL."""
    if hasattr(node_input, "parts"):
        repo_url = "".join(p.text for p in node_input.parts if p.text).strip()
    elif isinstance(node_input, dict) and "parts" in node_input:
        repo_url = "".join(p.get("text", "") for p in node_input["parts"]).strip()
    else:
        repo_url = str(node_input).strip()

    result = fetch_github_prs(repo_url)
    return Event(state={"prs_data": result}, output=result)


@node(name="assess_prs_node")
def assess_prs_node(ctx: Context, node_input: Any) -> Event:
    """Score each PR for risk and simulate its CI/CD pipeline execution."""
    prs = node_input.get("prs", [])

    assessments = []
    for pr in prs:
        assessment = calculate_pr_risk(pr)
        assessment["pipeline_execution"] = simulate_pipeline(assessment)
        assessments.append(assessment)

    result = {
        "repo_url":    node_input.get("repo_url", ""),
        "repo_name":   node_input.get("repo_name", ""),
        "assessments": assessments,
    }
    return Event(state={"assessments_data": result}, output=result)


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
                          generated_at           (string, ISO 8601: "2026-08-30T00:00:00Z")
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
""",
)


# ─── Workflow ────────────────────────────────────────────────────

pr_workflow = Workflow(
    name="pr_risk_workflow",
    edges=[
        ("START",         fetch_prs_node),
        (fetch_prs_node,  assess_prs_node),
        (assess_prs_node, synthesis_agent),
    ],
)


# ─── Apps ────────────────────────────────────────────────────────

input_app = App(
    name="input_agent",
    root_agent=input_agent,
)

main_app = App(
    name="support_agent",
    root_agent=pr_workflow,
)

# root_agent is required by `adk web` to discover and run this agent.
# When running via the web UI the user types the repo URL directly in
# the chat box; fetch_prs_node picks it up from the first message.
root_agent = pr_workflow
