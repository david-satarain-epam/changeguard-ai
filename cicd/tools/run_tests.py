"""
Tool: run_tests
Executes a test suite.
Simulated: realistic mock results with timing.
Live: triggers GitHub Actions workflow.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
import httpx
import yaml

logger = logging.getLogger("changeguard-cicd.run_tests")

POLICY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "workflow_policy.yaml")


def load_workflow_policy() -> dict:
    with open(POLICY_PATH, encoding="utf-8") as policy_file:
        return yaml.safe_load(policy_file)


async def _fetch_latest_workflow_run(client: httpx.AsyncClient, github_owner: str, github_repo: str, workflow_name: str) -> dict:
    """Fetch the most recent run for a workflow, returning its current status and metadata."""
    url = f"https://api.github.com/repos/{github_owner}/{github_repo}/actions/workflows/{workflow_name}/runs?per_page=5"
    response = await client.get(
        url,
        headers={
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if response.status_code != 200:
        return {"error": f"GitHub runs query failed: {response.status_code}", "details": response.text[:200]}

    payload = response.json()
    runs = payload.get("workflow_runs", [])
    if not runs:
        return {"status": "queued", "conclusion": None, "run_id": None, "html_url": None}

    latest = runs[0]
    return {
        "status": latest.get("status"),
        "conclusion": latest.get("conclusion"),
        "run_id": latest.get("id"),
        "html_url": latest.get("html_url"),
        "workflow_id": latest.get("workflow_id"),
        "created_at": latest.get("created_at"),
        "updated_at": latest.get("updated_at"),
    }


async def _fetch_workflow_jobs(client: httpx.AsyncClient, github_owner: str, github_repo: str, run_id: int | None) -> dict:
    """Return the real GitHub Actions job summary for a completed workflow run."""
    if not run_id:
        return {"total": 0, "successful": 0, "failed": 0}

    response = await client.get(
        f"https://api.github.com/repos/{github_owner}/{github_repo}/actions/runs/{run_id}/jobs?per_page=100",
        headers={
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if response.status_code != 200:
        return {"total": 0, "successful": 0, "failed": 0}

    jobs = response.json().get("jobs", [])
    return {
        "total": len(jobs),
        "successful": sum(job.get("conclusion") == "success" for job in jobs),
        "failed": sum(job.get("conclusion") in {"failure", "timed_out", "cancelled"} for job in jobs),
    }


def _duration_seconds_from_runs(created_at: str | None, updated_at: str | None) -> int:
    """Compute a usable duration value from GitHub Actions timestamps when available."""
    if not created_at or not updated_at:
        return 0
    try:
        from datetime import datetime
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return max(int((updated - created).total_seconds()), 0)
    except ValueError:
        return 0


def _build_workflow_result(action: str, pr_id: str, latest_run: dict, jobs: dict | None = None) -> dict:
    """Normalize GitHub workflow metadata into a report-friendly dict with details and duration."""
    status = str(latest_run.get("status") or "queued").lower()
    conclusion = str(latest_run.get("conclusion") or "").lower()
    run_id = latest_run.get("run_id")
    duration_seconds = _duration_seconds_from_runs(latest_run.get("created_at"), latest_run.get("updated_at"))
    jobs = jobs or {"total": 0, "successful": 0, "failed": 0}

    if conclusion == "success":
        detailed_status = "SUCCESS"
        details = f"GitHub Actions: success" + (f" • run #{run_id}" if run_id else "")
    elif conclusion in {"failure", "timed_out", "cancelled"}:
        detailed_status = conclusion.upper()
        details = f"GitHub Actions: {conclusion}"
        if run_id:
            details += f" • run #{run_id}"
    elif status in {"queued", "in_progress", "requested", "waiting", "pending", "running"}:
        detailed_status = status.upper()
        details = f"GitHub Actions: {status}"
        if run_id:
            details += f" • run #{run_id}"
    else:
        detailed_status = "UNKNOWN"
        details = "GitHub Actions workflow completed without a readable result"

    if action == "run_tests" and jobs["total"]:
        if conclusion == "success":
            details = f"GitHub Actions: {jobs['successful']}/{jobs['total']} test jobs passed"
        elif conclusion in {"failure", "timed_out", "cancelled"}:
            details = f"GitHub Actions: {jobs['failed']}/{jobs['total']} test jobs failed, timed out, or were cancelled"

    result = {
        "mode": "live",
        "workflow_status": status or "queued",
        "status": detailed_status,
        "conclusion": latest_run.get("conclusion"),
        "run_id": run_id,
        "html_url": latest_run.get("html_url"),
        "workflow_id": latest_run.get("workflow_id"),
        "workflow": action,
        "pr_id": pr_id,
        "duration_seconds": duration_seconds,
        "details": details,
        "message": details,
    }
    return result


async def dispatch_github_workflow(action: str, inputs: dict, pr_id: str) -> dict:
    """Dispatch the configured workflow and poll its real status back from GitHub Actions."""
    github_token = os.getenv("GITHUB_TOKEN")
    github_owner = os.getenv("GITHUB_OWNER")
    github_repo = os.getenv("GITHUB_REPO")
    policy = load_workflow_policy()
    workflow = policy["workflows"].get(action)
    github_ref = os.getenv("GITHUB_REF", policy.get("ref", "main"))
    missing = [name for name, value in {
        "GITHUB_TOKEN": github_token,
        "GITHUB_OWNER": github_owner,
        "GITHUB_REPO": github_repo,
        "workflow_policy": workflow,
        "GITHUB_REF": github_ref,
    }.items() if not value]
    if missing:
        return {
            "error": f"Missing CICD configuration: {', '.join(missing)}",
            "mode": "live",
            "workflow_status": "not_triggered",
            "pr_id": pr_id,
        }

    url = f"https://api.github.com/repos/{github_owner}/{github_repo}/actions/workflows/{workflow}/dispatches"
    payload = {"ref": github_ref, "inputs": {**inputs, "pr_id": pr_id}}

    dispatch_started = datetime.now(timezone.utc)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=payload,
        )

        if response.status_code != 204:
            return {
                "error": f"GitHub API returned {response.status_code}",
                "details": response.text[:200],
                "mode": "live",
                "workflow_status": "not_triggered",
                "workflow": workflow,
                "pr_id": pr_id,
            }

        latest_run = {"status": "queued", "conclusion": None, "run_id": None, "html_url": None, "workflow_id": None, "created_at": None, "updated_at": None}
        for attempt in range(12):
            if attempt > 0:
                await asyncio.sleep(5)
            latest_run = await _fetch_latest_workflow_run(client, github_owner, github_repo, workflow)
            if latest_run.get("status") == "completed":
                break

        jobs = await _fetch_workflow_jobs(client, github_owner, github_repo, latest_run.get("run_id"))
        result = _build_workflow_result(action, pr_id, latest_run, jobs)
        elapsed = int((datetime.now(timezone.utc) - dispatch_started).total_seconds())
        duration = result.get("duration_seconds") or elapsed
        if duration <= 0:
            duration = max(elapsed, 5)
        result["duration_seconds"] = duration
        if "details" in result and result.get("details") and "run #" not in result["details"] and result.get("run_id"):
            result["details"] = f"{result['details']} • run #{result['run_id']}"
        return result


async def run_tests_handler(test_plan: list, pr_id: str, mode: str = "simulated") -> dict:
    """
    Execute test suite.
    
    Args:
        test_plan: List of test names.
        pr_id: PR identifier.
        mode: "simulated" or "live".
    
    Returns:
        Test result dict.
    """
    logger.info("run_tests: %d tests for PR %s (mode: %s)", len(test_plan), pr_id, mode)

    if mode == "simulated":
        duration = len(test_plan) * 1.1
        await asyncio.sleep(min(duration / 10, 2))  # Accelerated for demo

        return {
            "total": len(test_plan),
            "passed": len(test_plan),
            "failed": 0,
            "skipped": 0,
            "duration_seconds": round(duration, 1),
            "details": f"{len(test_plan)}/{len(test_plan)} tests passed",
            "pr_id": pr_id,
            "mode": "simulated",
            "test_list": test_plan,
        }

    # Live mode — GitHub Actions trigger
    return await _trigger_github_workflow(test_plan, pr_id)


async def trigger_github_actions(test_plan: list, pr_id: str) -> dict:
    """Backward-compatible entry point for GitHub Actions workflow dispatch."""
    return await _trigger_github_workflow(test_plan, pr_id)


async def _trigger_github_workflow(test_plan: list, pr_id: str) -> dict:
    """Trigger the ChangeGuard test suite workflow on GitHub Actions."""
    return await dispatch_github_workflow("run_tests", {"test_plan": ", ".join(test_plan)}, pr_id)
    github_token = os.getenv("GITHUB_TOKEN")
    github_owner = os.getenv("GITHUB_OWNER")
    github_repo = os.getenv("GITHUB_REPO")
    github_workflow = os.getenv("GITHUB_WORKFLOW")
    github_ref = os.getenv("GITHUB_REF")

    missing = [
        name for name, value in {
            "GITHUB_TOKEN": github_token,
            "GITHUB_OWNER": github_owner,
            "GITHUB_REPO": github_repo,
            "GITHUB_WORKFLOW": github_workflow,
            "GITHUB_REF": github_ref,
        }.items() if not value
    ]
    if missing:
        message = f"Missing CICD configuration: {', '.join(missing)}"
        logger.error(message)
        return {
            "error": message,
            "pr_id": pr_id,
            "mode": "live",
            "workflow_status": "not_triggered",
        }

    url = (
        f"https://api.github.com/repos/{github_owner}/{github_repo}"
        f"/actions/workflows/{github_workflow}/dispatches"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={
                    "ref": github_ref,
                    "inputs": {
                        "test_plan": ", ".join(test_plan),
                        "pr_id": pr_id,
                    },
                },
            )

            if response.status_code == 204:
                logger.info("GitHub Actions workflow triggered")
                return {
                    "total": len(test_plan),
                    "passed": len(test_plan),
                    "failed": 0,
                    "skipped": 0,
                    "duration_seconds": 0,
                    "details": "GitHub Actions workflow triggered — check run for results",
                    "pr_id": pr_id,
                    "mode": "live",
                    "workflow_status": "triggered",
                    "workflow": github_workflow,
                }

            logger.error("GitHub API error: %s", response.status_code)
            return {
                "error": f"GitHub API returned {response.status_code}",
                "details": response.text[:200],
                "pr_id": pr_id,
                "mode": "live",
                "workflow_status": "not_triggered",
            }

        except httpx.HTTPError as e:
            logger.error("GitHub API call failed: %s", e)
            return {
                "error": str(e),
                "details": "GitHub Actions unreachable",
                "mode": "live",
            }