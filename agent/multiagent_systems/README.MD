# PR Risk Assessor — Multi-Agent System

An AI-powered tool that analyzes a GitHub Pull Request and produces a risk assessment, testing strategy, and deployment recommendation. It is built with [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/) and runs a sequential three-stage workflow powered by Gemini.

---

## How It Works

The system processes a PR URL through three stages, each feeding its output into the next:

```
GitHub PR URL
      │
      ▼
┌─────────────────┐
│  fetch_pr_node  │  Fetches PR metadata from the GitHub API
│  (deterministic)│  (title, description, changed files, diff size)
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│ calculate_risk_node  │  Scores the PR using rule-based logic
│    (deterministic)   │  (sensitive paths, diff size, file count)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   synthesis_agent    │  Gemini-powered agent that writes the
│       (Gemini)       │  final Markdown report with sign-off decision
└──────────────────────┘
```

1. **`fetch_pr_node`** — Calls the GitHub REST API to pull PR metadata. If the API is unreachable or the token is missing, it falls back to a built-in mock payload so you can still test the pipeline.

2. **`calculate_risk_node`** — Applies deterministic rules to produce a `risk_score` and `risk_level` (LOW / MEDIUM / HIGH). Rules check things like diff size, number of changed files, and whether sensitive paths (e.g. `db/migrations/`, `config/`, `.env`) were touched.

3. **`synthesis_agent`** — A Gemini agent that receives the risk report and writes a structured Markdown document covering: PR Overview, Risk Assessment, Testing Strategy, Deployment Strategy, and a final sign-off decision.

---

## Prerequisites

- Python 3.12 or 3.14
- A Google Cloud project with the Vertex AI or Gemini API enabled
- `gcloud` CLI authenticated (`gcloud auth application-default login`)
- A GitHub Personal Access Token (optional, but recommended to avoid rate limits)

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

Copy the template below into a file named `.env` in this directory and fill in your values:

```bash
# Use Vertex AI backend (set to "true") or direct Gemini API (set to "false")
GOOGLE_GENAI_USE_VERTEXAI=true

# Your Google Cloud project ID
GOOGLE_CLOUD_PROJECT=your-project-id

# Region for Vertex AI (e.g. us-central1)
GOOGLE_CLOUD_LOCATION=us-central1

# Gemini model to use (e.g. gemini-2.0-flash)
MODEL=gemini-2.0-flash

# GitHub Personal Access Token — prevents rate limiting on the GitHub API
GITHUB_TOKEN=ghp_your_token_here
```

> **Note:** `GITHUB_TOKEN` is optional. Without it, the tool still works but public repositories may hit the GitHub API rate limit (60 requests/hour for unauthenticated requests).

---

## Running the Tool

Pass any public GitHub Pull Request URL as the argument:

```bash
python3 test_runner.py https://github.com/owner/repo/pull/42
```

**Example:**

```bash
python3 test_runner.py https://github.com/alekz7/devops-repo/pull/1
```

---

## Sample Output

```
--- Running PR Risk Assessor ADK App ---
Input PR: https://github.com/alekz7/devops-repo/pull/1

Attempting to fetch PR details from: https://github.com/alekz7/devops-repo/pull/1

[Node Output]: {'title': 'Adding a comment to the repository', ...}

[Node Output]: {'risk_score': 0, 'risk_level': 'LOW', 'reasons': [], ...}

## PR Analysis and Release Strategy

### 1. PR Overview
- **Title**: Adding a comment to the repository
- **Description**: A purely documentation-related change adding comments to `main.py`.

### 2. Risk Assessment
- **Risk Level**: LOW
- **Risk Score**: 0
- **Reasons**: Minimal change (1 addition, 1 deletion) to a single non-sensitive file.

### 3. Recommended Testing Strategy
- Code review to verify the comment is accurate and follows project standards.
- Automated linting/static analysis to confirm no syntax issues were introduced.
- No functional, integration, or performance testing required.

### 4. Recommended Deployment Strategy
- **Direct Promotion**: Merge into target branch and include in the next standard release.
- No staged rollout or feature flags required.

### 5. Final Sign-off Decision
**APPROVED**
```

---

## Risk Scoring Rules

| Condition | Score Added |
|---|---|
| Diff > 500 lines | +3 |
| Diff 150–500 lines | +1 |
| > 10 files changed | +3 |
| 5–10 files changed | +1 |
| `db/migrations/` touched | +4 |
| `config/` touched | +3 |
| `.env` file touched | +5 |
| `security/` directory touched | +4 |
| `workflows/` (CI/CD) touched | +2 |

**Risk levels:** LOW (score 0–2) · MEDIUM (score 3–7) · HIGH (score 8+)

---

## Project Structure

```
multiagent_systems/
├── test_runner.py          # Entry point — run this with a PR URL
├── .env                    # Your environment variables (not committed)
├── support_agent/
│   ├── agent.py            # Workflow definition (nodes + Gemini agent)
│   ├── tools.py            # fetch_github_pr and calculate_pr_risk logic
│   └── requirements.txt    # Python dependencies
└── deployment/
    └── terraform/          # Infrastructure-as-code for cloud deployment
```
