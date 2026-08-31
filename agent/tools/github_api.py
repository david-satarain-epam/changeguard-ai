# agent/tools/github_api.py
"""Tools for fetching data from the GitHub API."""

import os
import re
import json
import urllib.request

def parse_repo_url(repo_url: str) -> tuple:
    """Extract (owner, repo) from a GitHub URL or 'owner/repo' string."""
    url = repo_url.strip().rstrip("/")
    match = re.match(r"https?://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?$", url)
    if match:
        return match.group(1), match.group(2)
    match = re.match(r"^([^/\s]+)/([^/\s]+)$", url)
    if match:
        return match.group(1), match.group(2)
    return None, None


def fetch_github_prs(repo_url: str) -> dict:
    """Fetch up to 10 most recent open PRs from a public GitHub repository."""
    owner, repo = parse_repo_url(repo_url)

    if not owner:
        print(f"Warning: cannot parse repo URL '{repo_url}'. Using mock data.")
        return get_mock_prs(repo_url)

    api_url = (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/pulls?state=open&per_page=10&sort=created&direction=desc"
    )
    headers = {
        "User-Agent": "ChangeGuard-AI-Agent",
        "Accept":     "application/vnd.github.v3+json",
    }
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            prs_data = json.loads(resp.read().decode())

        if not prs_data:
            print("No open PRs found. Using mock data.")
            return get_mock_prs(repo_url)

        prs = [
            {
                "pr_id":       str(pr["number"]),
                "pr_title":    pr.get("title", "Untitled PR"),
                "description": pr.get("body", "") or "",
                "pr_url":      pr.get("html_url", ""),
            }
            for pr in prs_data[:10]
        ]
        return {"repo_url": repo_url, "repo_owner": owner, "repo_name": repo, "prs": prs}

    except Exception as exc:
        print(f"Warning: GitHub API error ({exc}). Using mock data.")
        return get_mock_prs(repo_url)


def get_mock_prs(repo_url: str = "https://github.com/example/demo-repo") -> dict:
    """Return a realistic mock PR list used when the API is unavailable."""
    base = repo_url.rstrip("/")
    return {
        "repo_url":   repo_url,
        "repo_owner": "example",
        "repo_name":  "demo-repo",
        "prs": [
            {
                "pr_id":       "735",
                "pr_title":    "Add comments to the payment processing module",
                "description": "Added documentation comments to improve code readability. No functional changes.",
                "pr_url":      f"{base}/pull/735",
            },
            {
                "pr_id":       "801",
                "pr_title":    "Add caching layer for user profile service",
                "description": "Introduces Redis caching for user profile lookups. Adds new dependency on caching-service. New endpoint for cache invalidation.",
                "pr_url":      f"{base}/pull/801",
            },
            {
                "pr_id":       "620",
                "pr_title":    "Refactor authentication flow to support multi-factor authentication",
                "description": "Significant architectural change to auth-service. Affects all dependent services. Breaking change to token validation API.",
                "pr_url":      f"{base}/pull/620",
            },
            {
                "pr_id":       "812",
                "pr_title":    "Hotfix for P0 Production Incident in payment gateway",
                "description": "Critical hotfix for payment gateway connector. Breaking change to payment schema. Requires immediate deployment review.",
                "pr_url":      f"{base}/pull/812",
            },
        ],
    }
