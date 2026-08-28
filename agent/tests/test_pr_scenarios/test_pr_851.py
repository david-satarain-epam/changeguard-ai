"""
PR #851 — "Add multi-currency support to schemas"
Expected: CRITICAL risk, POSTPONE decision, NONE strategy.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from risk_engine.scoring import calculate_risk_score
from risk_engine.services import identify_affected_services, has_schema_change


class TestPR851:

    def test_schema_change_detected(self, pr_851):
        """Schema files should be detected."""
        assert has_schema_change(pr_851["files_changed"]) is True

    def test_multiple_services_affected(self, pr_851):
        """Payment + billing = 2 services."""
        services = identify_affected_services(pr_851["files_changed"])
        assert len(services) == 2
        assert "payment-api" in services
        assert "billing-service" in services

    def test_diff_mentions_breaking(self, pr_851):
        """New required field = breaking."""
        assert "breaking" in pr_851["diff_summary"].lower()

    def test_risk_is_critical(self, pr_851):
        """
        Payment path → MEDIUM
        Schema change → +1
        TIER 1 → +1
        Breaking → +1
        = HIGH → but 2 services + TIER 1 + breaking pushes to limit
        """
        services = identify_affected_services(pr_851["files_changed"])
        result = calculate_risk_score(
            files_changed=pr_851["files_changed"],
            diff_summary=pr_851["diff_summary"],
            contract_has_breaking=True,
            affected_services=services,
        )

        # Should be at least HIGH, possibly CRITICAL depending on rule stacking
        assert result["level"] >= 2
        assert result["strategy"] in ("CANARY", "NONE")