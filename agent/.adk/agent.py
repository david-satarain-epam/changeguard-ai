"""Agent for multiagent systems support."""

import os
from typing import Any
import dotenv
from google.adk import Agent
from google.adk import Context
from google.adk import Workflow
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.integrations.agent_registry import AgentRegistry
from google.adk.tools import VertexAiSearchTool
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.workflow import JoinNode, node

from .tools import find_similar_bugs, validate_tool_params


dotenv.load_dotenv()

# --- Config & Registry Initialization ---
MODEL = os.environ["MODEL"]
MCP_SERVER_NAME = os.environ["MCP_SERVER_NAME"]
PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ["GOOGLE_CLOUD_LOCATION"]

DATASTORE_LOCATION = os.environ["DATASTORE_LOCATION"]

MCP_SERVER_LOCATION = os.environ["MCP_SERVER_LOCATION"]
DATASTORE_ID = os.environ["DATASTORE_ID"]

# Verification Guard: Prevent API import crashes due to unconfigured MCP settings
if not MCP_SERVER_NAME or "your-mcp" in MCP_SERVER_NAME.lower() or MCP_SERVER_NAME == "None":
    raise ValueError(
        "\n"
        "========================================================================\n"
        "[ERROR] MCP_SERVER_NAME is not configured inside support_agent/.env!\n"
        "Please retrieve your MCP server name from the Active Registry console and\n"
        "update MCP_SERVER_NAME=agentregistry-... in your environment configuration.\n"
        "========================================================================"
    )

# Initialize Agent Registry
registry = AgentRegistry(project_id=PROJECT_ID, location=MCP_SERVER_LOCATION)


# --- Root Coordinator Agent ---
coordinator = Agent(
    name="coordinator",
    model=MODEL,
    instruction="""
    You are a DevSecOps incident coordinator.
    Analyze the user's reported incident query and extract:
    1. The main error message or exception name.
    2. Key stack trace lines if present.
    3. The affected programming language or framework.

    Provide a clean, focused search query containing these key terms.
    """,
    output_key="clean_query",
)


# --- Internal Knowledge Nodes ---

# TODO Task 4.1: Expose a Python function as a Workflow Node
@node(name="query_bq_node")
def query_bq(ctx: Context, node_input: Any) -> Event:
    """Runs semantic BQ vector search to find similar past incident reports."""
    result = find_similar_bugs(str(node_input))
    return Event(state={"query_bq_node": result}, output=result)


vais_tool = VertexAiSearchTool(
    data_store_id=(
        f"projects/{PROJECT_ID}/locations/{DATASTORE_LOCATION}/collections/"
        f"default_collection/dataStores/{DATASTORE_ID}"
    ),
    # TODO Task 3.3: Add the flag to bypass the multi tools limit here
    bypass_multi_tools_limit=True,
)


search_vais_agent = Agent(
    name="search_vais_agent",
    model=MODEL,
    instruction="""
    You are the Internal Documentation Searcher.
    Search the internal documentation using your Vertex AI Search tool for details matching the incident query: {clean_query}

    Output a clear list of matching pages, errors, or troubleshooting procedures you find.
    """,
    tools=[vais_tool],
    output_key="vais_search_data",
)


# --- Internal Analyst Agent ---
internal_analyst = Agent(
    name="internal_analyst",
    model=MODEL,
    instruction="""
    You are the Internal Knowledge Analyst.
    Analyze the provided internal BigQuery bug logs:

    {query_bq_node}

    
    And Vertex AI Search documentation:
    
    {vais_search_data}

    Summarize:
    1. Have we seen this issue internally? If so, what was the resolution?
    2. Do our internal manuals and runbooks provide standard operating procedures for this?

    Be factual and precise. Do not hallucinate any information not present in the sources.
    """,
    output_key="internal_response",
)


# --- External Web Search Agent ---

# TODO Task 3.4: Add the flag to bypass the multi tools limit here
# google_search = GoogleSearchTool()
google_search = GoogleSearchTool(bypass_multi_tools_limit=True)


web_search_agent = Agent(
    name="web_search_agent",
    model=MODEL,
    instruction="""
    You are the Web Search Agent.
    Your task is to search public developer sources (e.g. GitHub issues, StackOverflow, official documentation) using Google Search.
    Search for details about the following incident query: {clean_query}

    Provide a clear summary of public patched workarounds or documentation.
    """,
    tools=[google_search],
    # TODO Task 3.2: Bind your validate_tool_params callback here using the before_tool_callback parameter
    before_tool_callback=validate_tool_params,
    output_key="external_web_search_response",
)


# --- External MCP Knowledge Base Agent ---
# Define MCP Toolset for external documentation
developer_kb_mcp = registry.get_mcp_toolset(
    f"projects/{PROJECT_ID}/locations/{MCP_SERVER_LOCATION}/mcpServers/{MCP_SERVER_NAME}"
)

mcp_kb_agent = Agent(
    name="mcp_kb_agent",
    model=MODEL,
    instruction="""
    You are the Internal Knowledge Agent.
    Your task is to query the Developer KB MCP toolset for any internal developer documentation, guidelines, runbooks, or known incident reports matching this query: {clean_query}

    Provide a clear summary of internal findings.
    """,
    tools=[developer_kb_mcp],
    # TODO Task 3.2: Bind your validate_tool_params callback here using the before_tool_callback parameter
    before_tool_callback=validate_tool_params,
    output_key="external_mcp_kb_response",
)

# --- Join Node ---
merge_join = JoinNode(name="merge")


# --- Synthesis & Grounding Agent (Rules-Enforcer) ---
synthesis_agent = Agent(
    name="synthesis_agent",
    model=MODEL,
    instruction="""
    You are the Lead DevSecOps Synthesis and Grounding Agent.
    You are a rules-based agent that enforces internal knowledge prioritization.
    Your goal is to provide a final resolution recommendation for the user's reported incident.

    You have access to:
    - Internal Knowledge Report: {internal_response}
    - External Web Search findings: {external_web_search_response}
    - External KB findings: {external_mcp_kb_response}

    CRITICAL GROUNDING RULES:
    1. You MUST strictly prioritize internal knowledge over external web knowledge.
    2. If a valid internal incident resolution, runbook, or bug fix is found, use it as the primary solution.
    3. Only use external knowledge if:
       - No internal matching resolution, runbook, or bug is found.
       - The internal docs explicitly refer to external procedures.
    4. If there is any conflict between internal corporate policies/runbooks and external suggestions, the internal guidelines ALWAYS win.
    5. You must explicitly state your source attribution:
       - If the solution is based solely on internal sources, start with: "[Source: Internal Grounding]"
       - If based on external sources, start with: "[Source: External Grounding (No Internal Reference Found)]"
       - If hybrid, start with: "[Source: Hybrid Grounding]"

    Provide a structured resolution report with:
    - Source Attribution
    - Summary of the Issue
    - Recommended Action Steps (clear, numbered)
    - References (internal docs, bugs, or external links)
    """
)


# --- Main Workflow Definition ---
root_agent = Workflow(
    name="devsecops_workflow",
    edges=[
        # TODO Task 5: Define the Workflow Graph Edges.
        ('START', coordinator),
        (coordinator, query_bq),
        (query_bq, search_vais_agent),
        (coordinator, web_search_agent),
        (coordinator, mcp_kb_agent),
        (search_vais_agent, internal_analyst),
        (web_search_agent, merge_join),
        (mcp_kb_agent, merge_join),
        (internal_analyst, merge_join),
        (merge_join, synthesis_agent),
    ]
)

# --- App Definition ---
app = App(
    name="support_agent",
    root_agent=root_agent,
)
