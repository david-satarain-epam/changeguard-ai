"""Tests for run_tests tool."""

import pytest
from tools.run_tests import run_tests_handler


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