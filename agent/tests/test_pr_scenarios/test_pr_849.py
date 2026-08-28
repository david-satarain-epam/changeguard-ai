"""
PR #849 — "Add multi-provider OAuth2 + PKCE support"
Expected: HIGH risk, ROLLOUT decision, CANARY strategy.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from risk_engine.scoring import calculate_risk_score
from risk_engine.services import identify_affected_services, has_schema_change
from risk_engine.test_plan import generate_test_plan


class TestPR849:

    def test_files_include_auth(self, pr_849):
        """Auth service files should be changed."""
        assert any("src/auth" in f for f in pr_849["files_changed"])

    def test_multiple_files_changed(self, pr_849):
        """Should have at least 2 files changed."""
        assert len(pr_849["files_changed"]) >= 2

    def test_risk_is_high(self, pr_849):
        """
        Auth path → minimum HIGH
        TIER 1 → already at HIGH
        """
        services = identify_affected_services(pr_849["files_changed"])
        result = calculate_risk_score(
            files_changed=pr_849["files_changed"],
            diff_summary=pr_849["diff_summary"],
            affected_services=services,
        )

        assert result["score"] == "HIGH"
        assert result["decision"] == "ROLLOUT"
        assert result["strategy"] == "CANARY"

    def test_test_plan_includes_auth_tests(self, pr_849):
        """Test plan should include auth-specific tests."""
        services = identify_affected_services(pr_849["files_changed"])
        plan = generate_test_plan(services)

        assert any("oauth" in t for t in plan)
        assert any("token" in t for t in plan)