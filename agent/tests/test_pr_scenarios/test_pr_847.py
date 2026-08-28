"""
PR #847 — "Update refund endpoint"
Expected: HIGH risk, ROLLOUT decision, CANARY strategy.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from risk_engine.scoring import calculate_risk_score
from risk_engine.services import identify_affected_services, has_schema_change
from risk_engine.test_plan import generate_test_plan


class TestPR847:

    def test_files_include_payment(self, pr_847):
        """Should include payment service files."""
        assert any("src/payment" in f for f in pr_847["files_changed"])

    def test_files_include_schema(self, pr_847):
        """Schema file should be in changed files."""
        assert any("schema" in f for f in pr_847["files_changed"])

    def test_diff_mentions_breaking(self, pr_847):
        """Diff summary should mention breaking change."""
        assert "breaking" in pr_847["diff_summary"].lower()

    def test_services_include_payment_api(self, pr_847):
        """Payment API should be identified as affected."""
        services = identify_affected_services(pr_847["files_changed"])
        assert "payment-api" in services

    def test_schema_change_detected(self, pr_847):
        """Schema change should be detected."""
        assert has_schema_change(pr_847["files_changed"]) is True

    def test_risk_is_high(self, pr_847):
        """
        Deterministic scoring:
        - src/payment/** → MEDIUM
        - Schema change → +1
        - TIER 1 → +1
        - Breaking → +1
        = HIGH
        """
        services = identify_affected_services(pr_847["files_changed"])
        result = calculate_risk_score(
            files_changed=pr_847["files_changed"],
            diff_summary=pr_847["diff_summary"],
            contract_has_breaking=True,
            affected_services=services,
        )
        assert result["score"] == "HIGH"
        assert result["decision"] == "ROLLOUT"
        assert result["strategy"] == "CANARY"
        assert result["level"] == 2

    def test_test_plan_generated(self, pr_847):
        """Should generate test plan for payment-api."""
        services = identify_affected_services(pr_847["files_changed"])
        plan = generate_test_plan(services)

        assert len(plan) >= 4
        assert any("unit" in t for t in plan)
        assert any("integration" in t for t in plan)
        assert any("contract" in t for t in plan)
        assert any("smoke" in t for t in plan)