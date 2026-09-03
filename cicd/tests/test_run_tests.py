"""Tests for run_tests tool."""

import pytest
from tools.run_tests import dispatch_github_workflow, run_tests_handler


class TestRunTests:

    @pytest.mark.asyncio
    async def test_simulated_returns_all_passed(self):
        result = await run_tests_handler(
            ["unit:test_a", "unit:test_b", "integration:test_c"],
            "pr-847",
            mode="simulated",
        )
        assert result["total"] == 3
        assert result["passed"] == 3
        assert result["failed"] == 0
        assert result["mode"] == "simulated"

    @pytest.mark.asyncio
    async def test_simulated_has_duration(self):
        result = await run_tests_handler(["test"], "pr-847", mode="simulated")
        assert result["duration_seconds"] > 0

    @pytest.mark.asyncio
    async def test_dispatch_returns_final_workflow_result(self):
        import tools.run_tests as run_tests_module

        mp = pytest.MonkeyPatch()

        class FakeResponse:
            def __init__(self, status_code=200, payload=None):
                self.status_code = status_code
                self._payload = payload or {}

            def json(self):
                return self._payload

        class FakeClient:
            def __init__(self, *args, **kwargs):
                self.calls = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, *args, **kwargs):
                return FakeResponse(204)

            async def get(self, url, *args, **kwargs):
                if url.endswith("/jobs?per_page=100"):
                    return FakeResponse(200, {
                        "jobs": [
                            {"conclusion": "success"},
                            {"conclusion": "success"},
                            {"conclusion": "success"},
                        ]
                    })
                return FakeResponse(200, {
                    "workflow_runs": [{
                        "status": "completed",
                        "conclusion": "success",
                        "id": 321,
                        "html_url": "https://github.com/example/test/actions/runs/321",
                        "workflow_id": 99,
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:02:00Z",
                    }]
                })

        mp.setattr(run_tests_module.httpx, "AsyncClient", FakeClient)
        mp.setenv("GITHUB_TOKEN", "token")
        mp.setenv("GITHUB_OWNER", "example")
        mp.setenv("GITHUB_REPO", "demo")

        try:
            result = await dispatch_github_workflow("run_tests", {"test_plan": "unit"}, "pr-847")
        finally:
            mp.undo()

        assert result["workflow_status"] == "completed"
        assert result["conclusion"] == "success"
        assert result["run_id"] == 321
        assert result["details"] == "GitHub Actions: 3/3 test jobs passed • run #321"