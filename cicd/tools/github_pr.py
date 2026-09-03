"""GitHub pull-request operations executed by the Adaptive CICD MCP server."""

import json
import os
import re
import urllib.error
import urllib.request


def _parse_pr_url(pr_url: str) -> tuple[str, str, str]:
    """Extract owner, repository, and PR number from a GitHub PR URL."""
    match = re.search(
        r"https?://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)",
        str(pr_url or "").strip(),
    )
    if not match:
        raise ValueError("Expected a GitHub pull request URL: /owner/repo/pull/number")
    return match.groups()


def _github_write_request(url: str, method: str, payload: dict) -> dict:
    """Call a GitHub write endpoint using the CICD service credential."""
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        return {"ok": False, "error": "GITHUB_TOKEN is required by the CICD server for GitHub write operations."}

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method=method,
        headers={
            "User-Agent": "ChangeGuard-Adaptive-CICD",
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode()
            return {"ok": True, "status_code": response.status, "data": json.loads(body or "{}")}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        return {"ok": False, "error": f"GitHub API returned {exc.code}: {body}"}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": f"GitHub API request failed: {exc.reason}"}


async def comment_pr_handler(pr_url: str, body: str) -> dict:
    """Post an approved ChangeGuard assessment as a pull-request comment."""
    owner, repo, number = _parse_pr_url(pr_url)
    result = _github_write_request(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments",
        "POST",
        {"body": body},
    )
    if result["ok"]:
        comment = result["data"]
        return {
            "status": "SUCCESS",
            "comment_id": comment.get("id"),
            "html_url": comment.get("html_url"),
            "details": "ChangeGuard assessment posted to the pull request.",
        }
    return {"status": "FAILED", "error": result["error"], "details": f"Unable to post PR comment: {result['error']}"}


async def merge_pr_handler(pr_url: str, merge_method: str = "squash") -> dict:
    """Merge an approved pull request through GitHub's repository merge policy."""
    owner, repo, number = _parse_pr_url(pr_url)
    result = _github_write_request(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/merge",
        "PUT",
        {"merge_method": merge_method},
    )
    if result["ok"]:
        merge = result["data"]
        if merge.get("merged"):
            return {"status": "SUCCESS", "sha": merge.get("sha"), "details": merge.get("message", "Pull request merged.")}
        return {"status": "FAILED", "details": merge.get("message", "GitHub did not merge the pull request.")}
    return {"status": "FAILED", "error": result["error"], "details": f"Unable to merge PR: {result['error']}"}
