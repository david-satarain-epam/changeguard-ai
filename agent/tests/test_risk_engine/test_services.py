"""Tests for service identification."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from risk_engine.services import (
    identify_affected_services,
    has_schema_change,
    is_new_endpoint,
)


class TestIdentifyServices:

    def test_payment_files(self):
        svc = identify_affected_services(["src/payment/api.py", "src/payment/schema.py"])
        assert "payment-api" in svc

    def test_auth_files(self):
        svc = identify_affected_services(["src/auth/oauth.py"])
        assert "auth-service" in svc

    def test_multiple_services(self):
        svc = identify_affected_services([
            "src/payment/api.py", "src/auth/oauth.py", "src/notifications/template.html"
        ])
        assert len(svc) >= 3

    def test_unknown_file(self):
        svc = identify_affected_services(["README.md"])
        assert svc == ["unknown"]


class TestSchemaDetection:

    def test_schema_file(self):
        assert has_schema_change(["src/payment/schema.py"]) is True

    def test_openapi_file(self):
        assert has_schema_change(["openapi/baseline.json"]) is True

    def test_regular_file(self):
        assert has_schema_change(["src/payment/api.py"]) is False


class TestNewEndpoint:

    def test_batch_is_new(self):
        assert is_new_endpoint("NEW ENDPOINT: batch", ["src/payment/batch_refund.py"]) is True

    def test_zero_test_is_new(self):
        assert is_new_endpoint("ZERO test coverage", ["src/payment/api.py"]) is True

    def test_existing_not_new(self):
        assert is_new_endpoint("Updated logic", ["src/payment/api.py"]) is False