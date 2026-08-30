"""Tests for Policy Engine."""

import pytest


class TestPolicyEngine:

    def test_known_agent_allowed(self, policy_engine):
        allowed, reason = policy_engine.is_allowed(
            "change-impact-agent", "run_tests"
        )
        assert allowed is True
        assert reason == "Authorized"

    def test_known_agent_blocked_tool(self, policy_engine):
        allowed, reason = policy_engine.is_allowed(
            "change-impact-agent", "delete_database"
        )
        assert allowed is False
        assert "not allowed" in reason.lower()

    def test_rogue_agent_blocked(self, policy_engine):
        allowed, reason = policy_engine.is_allowed(
            "rogue-agent", "run_tests"
        )
        assert allowed is False
        assert "blocked" in reason.lower()

    def test_unknown_agent_blocked(self, policy_engine):
        allowed, reason = policy_engine.is_allowed(
            "unknown-agent-xyz", "run_tests"
        )
        assert allowed is False
        assert "not registered" in reason.lower()

    def test_all_context_tools_allowed(self, policy_engine):
        context_tools = [
            "compare_api_contracts",
            "find_affected_consumers",
            "get_business_criticality",
            "get_test_catalog",
        ]
        for tool in context_tools:
            allowed, _ = policy_engine.is_allowed("change-impact-agent", tool)
            assert allowed is True, f"Tool '{tool}' should be allowed"

    def test_all_execution_tools_allowed(self, policy_engine):
        exec_tools = [
            "run_tests",
            "deploy_canary",
            "monitor",
            "deploy_full",
            "rollback",
        ]
        for tool in exec_tools:
            allowed, _ = policy_engine.is_allowed("change-impact-agent", tool)
            assert allowed is True, f"Tool '{tool}' should be allowed"

    def test_policy_count(self, policy_engine):
        assert len(policy_engine.policies) >= 2