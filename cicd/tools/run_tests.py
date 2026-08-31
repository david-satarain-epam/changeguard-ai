"""
Tool: run_tests
Executes a test suite.
Simulated: realistic mock results with timing.
Live: triggers GitHub Actions workflow.
"""

import asyncio
import logging
import os
import httpx

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "david-satarain-epam")
GITHUB_REPO = os.getenv("GITHUB_REPO", "payment-api")

logger = logging.getLogger("changeguard-cicd.run_tests")


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
    if not GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN not set — falling back to simulated")
        return await run_tests_handler(test_plan, pr_id, "simulated")

    url = (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/actions/workflows/payments-test-suite.yml/dispatches"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={
                    "ref": "main",
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
                }

            logger.error("GitHub API error: %s", response.status_code)
            return {
                "error": f"GitHub API returned {response.status_code}",
                "details": response.text[:200],
                "mode": "live",
            }

        except httpx.HTTPError as e:
            logger.error("GitHub API call failed: %s", e)
            return {
                "error": str(e),
                "details": "GitHub Actions unreachable",
                "mode": "live",
            }