"""Tests for JIT Credential Generator."""

from datetime import datetime, timezone, timedelta


class TestJitCredentials:

    def test_generates_token(self, jit_creds):
        cred = jit_creds.generate("change-impact-agent", "run_tests")
        assert "token" in cred
        assert cred["token"].startswith("changeguard-jit-")

    def test_scoped_to_tool(self, jit_creds):
        cred = jit_creds.generate("change-impact-agent", "deploy_full")
        assert cred["scope"] == "deploy_full"

    def test_has_agent_id(self, jit_creds):
        cred = jit_creds.generate("change-impact-agent", "run_tests")
        assert cred["agent_id"] == "change-impact-agent"

    def test_default_ttl_15_minutes(self, jit_creds):
        cred = jit_creds.generate("change-impact-agent", "run_tests")
        assert cred["ttl_minutes"] == 15

    def test_custom_ttl(self, jit_creds):
        cred = jit_creds.generate("change-impact-agent", "run_tests", ttl_minutes=5)
        assert cred["ttl_minutes"] == 5

    def test_expires_in_future(self, jit_creds):
        cred = jit_creds.generate("change-impact-agent", "run_tests")
        expires = datetime.fromisoformat(cred["expires_at"])
        now = datetime.now(timezone.utc)
        assert expires > now

    def test_expires_within_ttl(self, jit_creds):
        cred = jit_creds.generate("change-impact-agent", "run_tests", ttl_minutes=10)
        expires = datetime.fromisoformat(cred["expires_at"])
        now = datetime.now(timezone.utc)
        diff = expires - now
        assert timedelta(minutes=9) < diff < timedelta(minutes=11)

    def test_unique_tokens(self, jit_creds):
        tokens = set()
        for _ in range(20):
            cred = jit_creds.generate("change-impact-agent", "run_tests")
            tokens.add(cred["token"])
        assert len(tokens) == 20