"""
Test: Deterministic risk scoring.
Same input → same output. Every time.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import (
    calculate_risk_score,
    identify_affected_services,
    has_schema_change,
    is_new_endpoint,
    RISK_LEVELS,
    PATH_RULES,
)


class TestPathRules:
    """Path-based minimum risk rules must be correct."""

    def test_payment_path_is_medium(self):
        assert any(
            path == "src/payment/" and min_risk == "MEDIUM"
            for path, min_risk, _ in PATH_RULES
        )

    def test_auth_path_is_high(self):
        assert any(
            path == "src/auth/" and min_risk == "HIGH"
            for path, min_risk, _ in PATH_RULES
        )

    def test_notifications_path_is_low(self):
        assert any(
            path == "src/notifications/" and min_risk == "LOW"
            for path, min_risk, _ in PATH_RULES
        )

    def test_all_paths_have_valid_risk_levels(self):
        for _, min_risk, _ in PATH_RULES:
            assert min_risk in RISK_LEVELS


class TestIdentifyServices:
    """File path → service mapping."""

    def test_payment_files_map_to_payment_api(self):
        services = identify_affected_services([
            "src/payment/api.py",
            "src/payment/schema.py",
        ])
        assert "payment-api" in services

    def test_auth_files_map_to_auth_service(self):
        services = identify_affected_services(["src/auth/oauth.py"])
        assert "auth-service" in services

    def test_multiple_services_detected(self):
        services = identify_affected_services([
            "src/payment/api.py",
            "src/auth/oauth.py",
            "src/notifications/template.html",
        ])
        assert len(services) >= 3
        assert "payment-api" in services
        assert "auth-service" in services

    def test_unknown_file_returns_unknown(self):
        services = identify_affected_services(["README.md"])
        assert services == ["unknown"]


class TestSchemaDetection:
    """Schema/contract change detection."""

    def test_schema_file_detected(self):
        assert has_schema_change(["src/payment/schema.py"]) is True

    def test_openapi_file_detected(self):
        assert has_schema_change(["openapi/baseline.json"]) is True

    def test_regular_file_not_detected(self):
        assert has_schema_change(["src/payment/api.py"]) is False

    def test_template_not_detected(self):
        assert has_schema_change(["src/notifications/template.html"]) is False


class TestNewEndpointDetection:
    """New endpoint detection (→ zero coverage)."""

    def test_batch_implies_new(self):
        assert is_new_endpoint("NEW ENDPOINT: batch refund", ["src/payment/batch_refund.py"]) is True

    def test_zero_test_implies_new(self):
        assert is_new_endpoint("ZERO test coverage", ["src/payment/api.py"]) is True

    def test_existing_endpoint_not_new(self):
        assert is_new_endpoint("Updated refund logic", ["src/payment/api.py"]) is False

    def test_new_file_keyword(self):
        assert is_new_endpoint("Add new feature", ["src/payment/new_endpoint.py"]) is True


class TestRiskCalculation:
    """End-to-end risk scoring."""

    def test_payment_schema_change_is_high(self):
        """Payment + schema change + TIER 1 = HIGH"""
        result = calculate_risk_score(
            files_changed=["src/payment/schema.py"],
            diff_summary="Breaking change to amount type",
            contract_has_breaking=True,
            affected_services=["payment-api"],
        )
        assert result["score"] == "HIGH"
        assert result["decision"] == "ROLLOUT"
        assert result["strategy"] == "CANARY"

    def test_notification_typo_is_low(self):
        """Notification only = LOW"""
        result = calculate_risk_score(
            files_changed=["src/notifications/template.html"],
            affected_services=["notification-service"],
        )
        assert result["score"] == "LOW"
        assert result["decision"] == "APPROVE"
        assert result["strategy"] == "DIRECT"

    def test_zero_coverage_is_critical(self):
        """Zero tests = CRITICAL → POSTPONE"""
        result = calculate_risk_score(
            files_changed=["src/payment/batch_refund.py"],
            diff_summary="New endpoint",
            affected_services=["payment-api"],
            test_coverage_zero=True,
        )
        assert result["score"] == "CRITICAL"
        assert result["decision"] == "POSTPONE"
        assert result["strategy"] == "NONE"

    def test_utils_only_is_low(self):
        """Utility changes = LOW"""
        result = calculate_risk_score(
            files_changed=["src/utils/logger.py"],
            affected_services=["all-services"],
        )
        assert result["score"] == "LOW"

    def test_auth_change_is_high(self):
        """Auth + TIER 1 = minimum HIGH"""
        result = calculate_risk_score(
            files_changed=["src/auth/oauth.py", "src/auth/token.py"],
            affected_services=["auth-service"],
        )
        assert result["score"] == "HIGH"

    def test_deterministic_same_result(self):
        """Same input → same output, 3 times."""
        args = {
            "files_changed": ["src/payment/schema.py", "src/billing/invoice.py"],
            "diff_summary": "Added currency field",
            "contract_has_breaking": True,
            "affected_services": ["payment-api", "billing-service"],
        }
        result1 = calculate_risk_score(**args)
        result2 = calculate_risk_score(**args)
        result3 = calculate_risk_score(**args)

        assert result1["score"] == result2["score"] == result3["score"]
        assert result1["decision"] == result2["decision"] == result3["decision"]