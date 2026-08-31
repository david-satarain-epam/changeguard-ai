"""Tests for monitor tool."""

import pytest
from tools.monitor import monitor_handler


class TestMonitor:

    @pytest.mark.asyncio
    async def test_healthy_by_default(self):
        result = await monitor_handler(5, "payment-api", mode="simulated")
        assert result["status"] == "HEALTHY"
        assert result["error_rate_pct"] <= 1.0

    @pytest.mark.asyncio
    async def test_degraded_with_high_error_rate(self):
        result = await monitor_handler(5, "payment-api", mode="simulated",
                                       simulated_error_rate=5.3)
        assert result["status"] == "DEGRADED"
        assert result["error_rate_pct"] == 5.3