# PR Risk Assessor — Multi-Agent System

An AI-powered tool that fetches all open Pull Requests from a GitHub repository, scores each one for deployment risk, and produces a structured JSON report with a recommended testing and deployment strategy. Built with [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/) and powered by Gemini.

---

## Architecture

The system runs in two phases. Phase 1 is a conversational agent that collects the repository URL from the user. Phase 2 is a three-node ADK Workflow that fetches, scores, and reports on every open PR.

```
╔══════════════════════════════════════════════════════════════╗
║  PHASE 1 — input_app                                         ║
║                                                              ║
║  ┌─────────────────────────────────────────────────────┐     ║
║  │  input_agent  (Gemini)                              │     ║
║  │                                                     │     ║
║  │  "Please provide your GitHub repository URL:"       │     ║
║  │   → validates and returns the URL                   │     ║
║  └─────────────────────────────────────────────────────┘     ║
╚══════════════════════════════════════════════════════════════╝
                           │
                    repo URL passed
                           │
                           ▼
╔══════════════════════════════════════════════════════════════╗
║  PHASE 2 — main_app  (ADK Workflow)                          ║
║                                                              ║
║  ┌─────────────────────────────────────────────────────┐     ║
║  │  fetch_prs_node  (deterministic)                    │     ║
║  │                                                     │     ║
║  │  GET /repos/{owner}/{repo}/pulls?state=open         │     ║
║  │  → top 10 open PRs (title, description, PR number)  │     ║
║  │  → falls back to mock data on any API failure       │     ║
║  └───────────────────────┬─────────────────────────────┘     ║
║                          │  list of PRs                      ║
║                          ▼                                   ║
║  ┌─────────────────────────────────────────────────────┐     ║
║  │  assess_prs_node  (deterministic)                   │     ║
║  │                                                     │     ║
║  │  For each PR:                                       │     ║
║  │    • keyword-based risk scoring                     │     ║
║  │    • service identification                         │     ║
║  │    • test plan generation                           │     ║
║  │    • CI/CD pipeline simulation (branched by risk)   │     ║
║  └───────────────────────┬─────────────────────────────┘     ║
║                          │  scored assessments               ║
║                          ▼                                   ║
║  ┌─────────────────────────────────────────────────────┐     ║
║  │  synthesis_agent  (Gemini)                          │     ║
║  │                                                     │     ║
║  │  • writes reasoning narrative for each PR           │     ║
║  │  • renders the report_html placeholder card         ║     ║
║  │  • assembles the final JSON array                   │     ║
║  └─────────────────────────────────────────────────────┘     ║
╚══════════════════════════════════════════════════════════════╝
                           │
                    JSON array output
```

### Design principles

- **Deterministic first, LLM last.** All risk scoring, service identification, pipeline simulation, and structured data assembly happen in deterministic Python nodes. Gemini only fills in the narrative (`reasoning`) and the HTML card — fields that benefit from natural language.
- **Mock fallback at every boundary.** If the GitHub API is unavailable or returns no PRs, the system substitutes realistic mock data so the full pipeline always runs.
- **No credentials required.** Works with any public GitHub repository without a token.

---

## Workflow Nodes in Detail

### `input_agent` (Gemini Agent — Phase 1)

A standalone conversational agent that runs before the main workflow. It receives the user's message and either returns a valid GitHub repository URL or asks for one. Runs as its own ADK `App` so the conversation can complete before the workflow starts.

### `fetch_prs_node` (deterministic)

Calls the GitHub REST API list endpoint:
```
GET https://api.github.com/repos/{owner}/{repo}/pulls?state=open&per_page=10&sort=created&direction=desc
```
Returns at most 10 PRs with: `pr_id`, `pr_title`, `description`, and `pr_url`. Changed files and diff sizes are **not** fetched (would require one API call per PR). Falls back to a built-in set of 4 mock PRs if the request fails or the repository has no open PRs.

### `assess_prs_node` (deterministic)

Loops over every PR returned by `fetch_prs_node` and runs two functions:

**`calculate_pr_risk`** — scores risk from title and description using keyword matching:

| Step | Rule | Effect |
|---|---|---|
| 1 | High-risk keywords in text | Baseline → HIGH |
| 2 | Medium-risk keywords in text | Baseline → MEDIUM |
| 3 | Neither | Baseline → LOW |
| 4 | Breaking change keywords detected | +1 level |
| 5 | TIER 1 service identified | +1 level |
| 6 | 3 or more services affected | +1 level |

Risk levels cap at CRITICAL. The decision and deployment strategy are derived from the final level:

| Risk | Decision | Strategy |
|---|---|---|
| LOW | APPROVE | DIRECT |
| MEDIUM | APPROVE | GATED |
| HIGH | ROLLOUT | CANARY |
| CRITICAL | POSTPONE | NONE |

**`simulate_pipeline`** — builds the `pipeline_execution` block based on the deployment strategy:

| Strategy | Stages |
|---|---|
| DIRECT | test_suite → security_scan → deploy_full |
| GATED | test_suite → security_scan → manual_approval → deploy_full |
| CANARY | test_suite → security_scan → deploy_canary → monitoring → deploy_full |
| NONE | *(empty — deployment postponed)* |

### `synthesis_agent` (Gemini Agent — Phase 2)

Receives the full assessment data via ADK state injection (`{assessments_data}`). Its responsibilities are narrow: write a 2–3 sentence `reasoning` for each PR and render the `report_html` placeholder card. All numeric fields, risk scores, decisions, and pipeline data are copied unchanged from the deterministic output.

---

## Output Format

Each PR in the final JSON array has four top-level keys:

```json
{
  "report_html": "<div ...>...</div>",
  "report_metadata": {
    "workflow_id": "wf-20260830-735",
    "pr_id": "735",
    "pr_title": "Add comments to the payment processing module",
    "generated_at": "2026-08-30T00:00:00Z",
    "total_duration_seconds": 102,
    "status": "SUCCESS"
  },
  "impact_analysis": {
    "risk_score": "LOW",
    "decision": "APPROVE",
    "strategy": "DIRECT",
    "affected_services": ["main-app-repo"],
    "affected_consumers_count": 0,
    "reasoning": "...",
    "escalation_log": ["Non-functional or low-impact change"],
    "coverage_gap_detected": false,
    "context_sources": {
      "api_contract_checked": false,
      "consumers_queried": false,
      "criticality_checked": true,
      "test_catalog_queried": true
    }
  },
  "pipeline_execution": {
    "stages": [
      { "name": "test_suite",    "status": "PASSED",    "duration_seconds": 47 },
      { "name": "security_scan", "status": "PASSED",    "duration_seconds": 25 },
      { "name": "deploy_full",   "status": "COMPLETED", "duration_seconds": 30 }
    ],
    "final_status": "SUCCESS",
    "total_duration_seconds": 102
  }
}
```

---

## Prerequisites

- Python 3.12 or 3.14
- A Google Cloud project with the Vertex AI or Gemini API enabled
- `gcloud` CLI authenticated (`gcloud auth application-default login`)

---

## Setup

### 1. Navigate to this directory

```bash
cd agent/multiagent_systems
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r support_agent/requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in this directory:

```bash
# Use Vertex AI backend (true) or direct Gemini API (false)
GOOGLE_GENAI_USE_VERTEXAI=true

# Your Google Cloud project ID
GOOGLE_CLOUD_PROJECT=your-project-id

# Region for Vertex AI (e.g. us-central1)
GOOGLE_CLOUD_LOCATION=us-central1

# Gemini model to use
MODEL=gemini-2.0-flash
```

> `GITHUB_TOKEN` is not required. The tool targets public repositories using the unauthenticated GitHub API (60 req/hour limit).

---

## Running the Tool

### Conversational mode — agent asks for the URL

```bash
python3 test_runner.py
```

```
--- ChangeGuard AI: PR Risk Assessor ---
Please provide your GitHub repository URL (e.g., https://github.com/owner/repo):
> https://github.com/alekz7/devops-repo

--- Analyzing repository: https://github.com/alekz7/devops-repo ---
...
```

### Direct mode — pass the URL as an argument

```bash
python3 test_runner.py https://github.com/alekz7/devops-repo
```

---

## Project Structure

```
multiagent_systems/
├── test_runner.py              # Entry point
├── .env                        # Environment variables (not committed)
├── support_agent/
│   ├── agent.py                # input_agent, workflow nodes, synthesis_agent, both Apps
│   ├── tools.py                # fetch_github_prs, calculate_pr_risk, simulate_pipeline
│   └── requirements.txt        # Python dependencies
└── deployment/
    └── terraform/              # Infrastructure-as-code for cloud deployment
```
