"""Tests for deterministic risk scoring."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from risk_engine.scoring import calculate_risk_score


class TestRiskScoring:

    def test_payment_schema_breaking_is_high(self):
        result = calculate_risk_score(
            files_changed=["src/payment/schema.py"],
            diff_summary="Breaking change",
            contract_has_breaking=True,
            affected_services=["payment-api"],
        )
        assert result["score"] == "HIGH"
        assert result["decision"] == "ROLLOUT"
        assert result["strategy"] == "CANARY"

    def test_notification_typo_is_low(self):
        result = calculate_risk_score(
            files_changed=["src/notifications/template.html"],
            affected_services=["notification-service"],
        )
        assert result["score"] == "LOW"
        assert result["decision"] == "APPROVE"
        assert result["strategy"] == "DIRECT"

    def test_utils_change_is_low(self):
        result = calculate_risk_score(
            files_changed=["src/utils/logger.py"],
            affected_services=["all-services"],
        )
        assert result["score"] == "LOW"

    def test_auth_change_is_high(self):
        result = calculate_risk_score(
            files_changed=["src/auth/oauth.py", "src/auth/token.py"],
            affected_services=["auth-service"],
        )
        assert result["score"] == "HIGH"

    def test_zero_coverage_is_critical(self):
        result = calculate_risk_score(
            files_changed=["src/payment/batch_refund.py"],
            affected_services=["payment-api"],
            test_coverage_zero=True,
        )
        assert result["score"] == "CRITICAL"
        assert result["decision"] == "POSTPONE"
        assert result["strategy"] == "NONE"

    def test_multiple_services_escalation(self):
        result = calculate_risk_score(
            files_changed=["src/payment/api.py", "src/auth/oauth.py", "src/billing/invoice.py"],
            affected_services=["payment-api", "auth-service", "billing-service"],
        )
        assert result["level"] >= 2  # At least HIGH

    def test_tier_1_escalation(self):
        result = calculate_risk_score(
            files_changed=["src/payment/api.py"],
            affected_services=["payment-api"],
        )
        # payment-api is TIER 1 → +1
        assert result["level"] >= 1  # At least MEDIUM