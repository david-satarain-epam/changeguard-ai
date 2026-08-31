"""Tests for rollback tool."""

import pytest
from tools.rollback import rollback_handler


class TestRollback:

    @pytest.mark.asyncio
    async def test_rollback_restores_traffic(self):
        result = await rollback_handler("payment-api", "v2.1", mode="simulated")
        assert result["status"] == "ROLLED_BACK"
        assert result["traffic_restored_pct"] == 100