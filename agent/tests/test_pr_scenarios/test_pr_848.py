"""
PR #848 — "Fix typo in notification template"
Expected: LOW risk, APPROVE decision, DIRECT strategy.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from risk_engine.scoring import calculate_risk_score
from risk_engine.services import identify_affected_services, has_schema_change


class TestPR848:

    def test_files_are_notification_only(self, pr_848):
        """All changed files should be in notifications."""
        assert all("notification" in f for f in pr_848["files_changed"])

    def test_no_schema_change(self, pr_848):
        """Template change should NOT be a schema change."""
        assert has_schema_change(pr_848["files_changed"]) is False

    def test_risk_is_low(self, pr_848):
        """Notification only + no schema = LOW."""
        services = identify_affected_services(pr_848["files_changed"])
        result = calculate_risk_score(
            files_changed=pr_848["files_changed"],
            diff_summary=pr_848["diff_summary"],
            affected_services=services,
        )

        assert result["score"] == "LOW"
        assert result["decision"] == "APPROVE"
        assert result["strategy"] == "DIRECT"
        assert result["level"] == 0

    def test_services_are_notification(self, pr_848):
        """Only notification-service should be affected."""
        services = identify_affected_services(pr_848["files_changed"])
        assert services == ["notification-service"]