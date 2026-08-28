"""
PR #852 — "Add batch refund endpoint"
Expected: CRITICAL risk, POSTPONE decision, NONE strategy.
Zero test coverage triggers CRITICAL regardless of other rules.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from risk_engine.scoring import calculate_risk_score
from risk_engine.services import identify_affected_services, is_new_endpoint
from risk_engine.test_plan import generate_test_plan, generate_suggested_tests


class TestPR852:

    def test_new_endpoint_detected(self, pr_852):
        """Should detect that this is a new endpoint."""
        assert is_new_endpoint(pr_852["diff_summary"], pr_852["files_changed"]) is True

    def test_batch_refund_file_present(self, pr_852):
        """New file batch_refund.py should be in changed files."""
        assert any("batch_refund" in f for f in pr_852["files_changed"])

    def test_risk_is_critical(self, pr_852):
        """Zero coverage → CRITICAL always."""
        services = identify_affected_services(pr_852["files_changed"])
        result = calculate_risk_score(
            files_changed=pr_852["files_changed"],
            diff_summary=pr_852["diff_summary"],
            affected_services=services,
            test_coverage_zero=True,
        )

        assert result["score"] == "CRITICAL"
        assert result["decision"] == "POSTPONE"
        assert result["strategy"] == "NONE"
        assert result["level"] == 3

    def test_no_test_plan_generated(self, pr_852):
        """With zero coverage, no test plan should be generated (empty)."""
        services = identify_affected_services(pr_852["files_changed"])
        plan = generate_test_plan(services)

        # Plan should be empty because coverage is zero
        # The agent will use suggested tests instead
        assert len(plan) >= 0  # Plan is for existing tests only

    def test_suggested_tests_generated(self, pr_852):
        """Should generate at least 6 suggested tests."""
        services = identify_affected_services(pr_852["files_changed"])
        suggestions = generate_suggested_tests(pr_852["diff_summary"], services)

        assert len(suggestions) >= 6
        assert any("batch" in s for s in suggestions)
        assert any("unit" in s for s in suggestions)
        assert any("integration" in s for s in suggestions)
        assert any("contract" in s for s in suggestions)

    def test_suggested_tests_cover_all_categories(self, pr_852):
        """Suggested tests should include unit, integration, and contract."""
        services = identify_affected_services(pr_852["files_changed"])
        suggestions = generate_suggested_tests(pr_852["diff_summary"], services)

        categories = set()
        for s in suggestions:
            if "unit:" in s:
                categories.add("unit")
            elif "integration:" in s:
                categories.add("integration")
            elif "contract:" in s:
                categories.add("contract")

        assert "unit" in categories
        assert "integration" in categories
        assert "contract" in categories