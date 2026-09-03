"""Read and validate one GitHub pull request for ChangeGuard analysis."""

import json
import os
import re
import urllib.error
import urllib.request


def fetch_github_pr(pr_url: str) -> dict:
    """Fetch one open, unmerged pull request and its changed files from GitHub."""
    match = re.search(
        r"https?://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)",
        str(pr_url or "").strip(),
    )
    if not match:
        raise ValueError("Expected a GitHub pull request URL: /owner/repo/pull/number")

    owner, repo, number = match.groups()
    headers = {
        "User-Agent": "ChangeGuard-AI-Agent",
        "Accept": "application/vnd.github+json",
    }
    if github_token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {github_token}"

    def get_json(url: str) -> dict | list:
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise ValueError(
                    f"PR #{number} was not found in {owner}/{repo}. Provide an existing, open GitHub pull request URL."
                ) from exc
            if exc.code in {401, 403}:
                raise ValueError(
                    f"ChangeGuard cannot read PR #{number} in {owner}/{repo}. Check GitHub access."
                ) from exc
            raise ValueError(
                f"GitHub could not read PR #{number} in {owner}/{repo} (HTTP {exc.code}). Try again later."
            ) from exc
        except urllib.error.URLError as exc:
            raise ValueError(
                f"GitHub could not be reached while reading PR #{number} in {owner}/{repo}: {exc.reason}"
            ) from exc

    pr_data = get_json(f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}")
    if pr_data.get("merged_at"):
        raise ValueError(f"PR #{number} in {owner}/{repo} is already merged. Provide an open pull request URL.")
    if pr_data.get("state") != "open":
        raise ValueError(
            f"PR #{number} in {owner}/{repo} is {pr_data.get('state', 'closed')}. Provide an open pull request URL."
        )

    files_data = get_json(f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/files?per_page=100")
    return {
        "pr_id": str(pr_data["number"]),
        "pr_title": pr_data.get("title", "Untitled PR"),
        "description": pr_data.get("body", "") or "",
        "pr_url": pr_data.get("html_url", str(pr_url)),
        "changed_files": [item["filename"] for item in files_data],
        "repo_owner": owner,
        "repo_name": repo,
    }
