"""Agent for Pull Request Risk Assessment and Deployment Strategy."""

import os
from typing import Any
import dotenv
from google.adk import Agent
from google.adk import Context
from google.adk import Workflow
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.workflow import node

from .tools import fetch_github_pr, calculate_pr_risk

dotenv.load_dotenv()

# --- Config & Initialization ---
MODEL = os.environ.get("MODEL", "gemini-3.5-flash")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

# --- Workflow Nodes ---

@node(name="fetch_pr_node")
def fetch_pr_node(ctx: Context, node_input: Any) -> Event:
    """Workflow node that fetches PR data from GitHub URL or returns mock data on failure."""
    # Extract the text part from Content if applicable
    if hasattr(node_input, 'parts'):
        pr_url = "".join(part.text for part in node_input.parts if part.text)
    elif isinstance(node_input, dict) and "parts" in node_input:
        pr_url = "".join(part.get("text", "") for part in node_input["parts"] if part.get("text"))
    else:
        pr_url = str(node_input).strip()

    result = fetch_github_pr(pr_url)
    return Event(state={"pr_data": result}, output=result)

@node(name="calculate_risk_node")
def calculate_risk_node(ctx: Context, node_input: Any) -> Event:
    """Workflow node that calculates risk from PR data using deterministic rules."""
    # node_input is the output of fetch_pr_node
    result = calculate_pr_risk(node_input)
    return Event(state={"risk_data": result}, output=result)

# --- Synthesis Agent ---
synthesis_agent = Agent(
    name="synthesis_agent",
    model=MODEL,
    instruction="""
    You are the Lead Release Engineer and QA Strategy Planner.
    You will receive a Pull Request risk analysis report:
    
    {risk_data}
    
    Your goal is to synthesize the final decision and recommend a comprehensive testing and deployment strategy.
    
    Format your final response in clear Markdown with the following sections:
    1. **PR Overview**: Title and general description.
    2. **Risk Assessment**: The calculated Risk Level, Score, and specific reasons triggering the risk.
    3. **Recommended Testing Strategy**: Specific types of testing required (e.g., unit tests, automated integration tests, manual QA, database migrations testing).
    4. **Recommended Deployment Strategy**: How to safely deploy this change (e.g., direct promotion, blue-green staging, canary release, feature-flag guarded).
    5. **Final Sign-off Decision**: Clear determination (e.g., APPROVED / NEEDS MANUAL REVIEW / AUDIT REQUIRED).
    """
)

# --- Main Workflow Definition ---
root_agent = Workflow(
    name="pr_risk_workflow",
    edges=[
        ('START', fetch_pr_node),
        (fetch_pr_node, calculate_risk_node),
        (calculate_risk_node, synthesis_agent),
    ]
)

# --- App Definition ---
app = App(
    name="support_agent",
    root_agent=root_agent,
)
