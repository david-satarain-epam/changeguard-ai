"""
PR #850 — "Refactor logger for Cloud Logging"
Expected: LOW risk, APPROVE decision, DIRECT strategy.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from risk_engine.scoring import calculate_risk_score
from risk_engine.services import identify_affected_services, has_schema_change


class TestPR850:

    def test_files_are_utils_only(self, pr_850):
        """Only utility files should be changed."""
        assert all("utils" in f for f in pr_850["files_changed"])

    def test_no_schema_change(self, pr_850):
        """Utility refactor should NOT be a schema change."""
        assert has_schema_change(pr_850["files_changed"]) is False

    def test_risk_is_low(self, pr_850):
        """Utils only + no schema = LOW."""
        services = identify_affected_services(pr_850["files_changed"])
        result = calculate_risk_score(
            files_changed=pr_850["files_changed"],
            diff_summary=pr_850["diff_summary"],
            affected_services=services,
        )

        assert result["score"] == "LOW"
        assert result["decision"] == "APPROVE"
        assert result["strategy"] == "DIRECT"

    def test_no_breaking_in_diff(self, pr_850):
        """Diff should explicitly say no breaking changes."""
        assert "no breaking" in pr_850["diff_summary"].lower()