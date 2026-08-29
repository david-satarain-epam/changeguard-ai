"""Tools for Pull Request Risk Assessment."""

import os
import re
import json
import urllib.request
import urllib.error

def fetch_github_pr(pr_url: str) -> dict:
    """Fetches Pull Request details from GitHub. 
    
    If the request fails or is unauthorized, logs the error and returns a mock PR payload.
    
    Args:
        pr_url: The full URL to the pull request, e.g. https://github.com/owner/repo/pull/1
    """
    print(f"Attempting to fetch PR details from: {pr_url}")
    
    # Parse URL: expect https://github.com/{owner}/{repo}/pull/{num}
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
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
