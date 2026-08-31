"""
Main tool: analyze_pr
Receives PR payload → returns risk assessment.
"""

import logging
from google.adk.tools import FunctionTool, ToolContext
import json
import os
import re
import urllib.request

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
        "pr_title": title,
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


FunctionTool(func=analyze_pr_handler)

def fetch_github_pr(pr_url: str) -> dict:
    """Fetches Pull Request details from GitHub. 
    
    If the request fails or is unauthorized, logs the error and returns a mock PR payload.
    
    Args:
        pr_url: The full URL to the pull request, e.g. https://github.com/owner/repo/pull/1
    """
    raw_value = str(pr_url or "").strip()
    print(f"Attempting to fetch PR details from: {raw_value}")

    # Accept URLs embedded inside a sentence, with or without the https:// prefix.
    normalized = raw_value
    url_match = re.search(r"https?://github\.com/[^\s)\]>]+/pull/\d+", normalized)
    if not url_match:
        url_match = re.search(r"github\.com/[^\s)\]>]+/pull/\d+", normalized)
        if url_match:
            normalized = "https://" + url_match.group(0)
        else:
            print("Console Warning: Invalid GitHub PR URL format. Using mock PR data.")
            return get_mock_pr()
    else:
        normalized = url_match.group(0)

    match = re.search(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", normalized)
    if not match:
        print("Console Warning: Invalid GitHub PR URL format. Using mock PR data.")
        return get_mock_pr()

    owner, repo, pr_num = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}"
    files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}/files"
    
    headers = {
        "User-Agent": "PR-Risk-Assessor-Agent"
    }
    
    # Check for github token in environment variables
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"
        
    try:
        # Fetch PR main metadata
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            pr_data = json.loads(response.read().decode())
            
        # Fetch PR changed files
        req_files = urllib.request.Request(files_url, headers=headers)
        with urllib.request.urlopen(req_files, timeout=5) as response_files:
            files_data = json.loads(response_files.read().decode())
            
        changed_files = [f["filename"] for f in files_data]
        
        return {
            "title": pr_data.get("title", ""),
            "description": pr_data.get("body", "") or "",
            "additions": pr_data.get("additions", 0),
            "deletions": pr_data.get("deletions", 0),
            "changed_files_count": pr_data.get("changed_files", 0),
            "changed_files": changed_files
        }
        
    except Exception as e:
        print(f"Console Warning: GitHub API connection failed ({e}). Simulating fallback to mock PR.")
        return get_mock_pr()

def get_mock_pr() -> dict:
    """Returns a mock Pull Request payload for demonstration."""
    return {
        "title": "Mock PR: Update stripe payment gateway and config",
        "description": "Refactors the payment logic to migrate from legacy processor to Stripe API. Updates keys in prod config.",
        "additions": 482,
        "deletions": 115,
        "changed_files_count": 4,
        "changed_files": [
            "src/payments/stripe.py",
            "src/payments/legacy.py",
            "config/production.json",
            "db/migrations/20260828_add_stripe_fields.sql"
        ]
    }

def calculate_pr_risk(pr_data: dict) -> dict:
    """Calculates PR risk using deterministic rules based on changed files and diff size."""
    additions = pr_data.get("additions", 0)
    deletions = pr_data.get("deletions", 0)
    changed_files_count = pr_data.get("changed_files_count", 0)
    changed_files = pr_data.get("changed_files", [])
    
    risk_score = 0
    reasons = []
    
    # 1. Diff size rules
    total_lines = additions + deletions
    if total_lines > 500:
        risk_score += 3
        reasons.append(f"Large diff size ({total_lines} lines changed)")
    elif total_lines > 150:
        risk_score += 1
        reasons.append(f"Moderate diff size ({total_lines} lines changed)")
        
    # 2. Changed files count rule
    if changed_files_count > 10:
        risk_score += 3
        reasons.append(f"High number of changed files ({changed_files_count} files)")
    elif changed_files_count > 5:
        risk_score += 1
        reasons.append(f"Moderate number of changed files ({changed_files_count} files)")
        
    # 3. Sensitive file types or pathways
    sensitive_patterns = {
        "db/migrations": (4, "Database migrations detected (requires schema validation)"),
        "config/": (3, "Configuration files modified"),
        ".env": (5, "Environment variables file modified"),
        "security": (4, "Security related directories/files modified"),
        "workflows/": (2, "CI/CD workflow files modified"),
    }
    
    for file_path in changed_files:
        for pattern, (weight, message) in sensitive_patterns.items():
            if pattern in file_path:
                risk_score += weight
                if message not in reasons:
                    reasons.append(message)
                break  # match only one rule per file to keep it balanced
                
    # Categorize Risk
    if risk_score >= 8:
        risk_level = "HIGH"
    elif risk_score >= 3:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
        
    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "reasons": reasons,
        "pr_details": pr_data
    }
