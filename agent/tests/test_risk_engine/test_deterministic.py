"""Deterministic: same input → same output."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from risk_engine.scoring import calculate_risk_score


class TestDeterministic:

    def test_same_input_same_output(self):
        args = {
            "files_changed": ["src/payment/schema.py"],
            "diff_summary": "Breaking change to amount type",
            "contract_has_breaking": True,
            "affected_services": ["payment-api"],
        }

        r1 = calculate_risk_score(**args)
        r2 = calculate_risk_score(**args)
        r3 = calculate_risk_score(**args)

        assert r1["score"] == r2["score"] == r3["score"]
        assert r1["decision"] == r2["decision"] == r3["decision"]
        assert r1["strategy"] == r2["strategy"] == r3["strategy"]
        assert r1["level"] == r2["level"] == r3["level"]

    def test_no_random_variation(self):
        """Run 10 times. All must be identical."""
        args = {
            "files_changed": ["src/auth/oauth.py"],
            "affected_services": ["auth-service"],
        }

        results = [calculate_risk_score(**args) for _ in range(10)]
        first = results[0]

        for r in results[1:]:
            assert r["score"] == first["score"]
            assert r["level"] == first["level"]