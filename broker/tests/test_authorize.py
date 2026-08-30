"""Integration tests for authorize_tool_call."""


class TestAuthorize:

    def test_authorized_agent_returns_jit_credential(self, policy_engine, jit_creds, audit_logger):
        from broker.tools.authorize import create_authorize_handler
        import asyncio

        handler = create_authorize_handler(policy_engine, jit_creds, audit_logger)
        result = asyncio.run(handler(
            {
                "agent_id": "change-impact-agent",
                "tool_name": "run_tests",
                "session_id": "pr-847",
                "payload": {"test_plan": ["smoke"]},
            },
            context=None,
        ))

        assert result["authorized"] is True
        assert result["jit_credential"].startswith("changeguard-jit-")
        assert result["audit_id"] is not None

    def test_rogue_agent_blocked(self, policy_engine, jit_creds, audit_logger):
        from broker.tools.authorize import create_authorize_handler
        import asyncio

        handler = create_authorize_handler(policy_engine, jit_creds, audit_logger)
        result = asyncio.run(handler(
            {
                "agent_id": "rogue-agent",
                "tool_name": "deploy_full",
                "session_id": "unknown",
                "payload": {},
            },
            context=None,
        ))

        assert result["authorized"] is False
        assert result["action_taken"] == "BLOCKED"
        assert "jit_credential" not in result

    def test_blocked_call_creates_audit_entry(self, policy_engine, jit_creds, audit_logger):
        from broker.tools.authorize import create_authorize_handler
        import asyncio

        handler = create_authorize_handler(policy_engine, jit_creds, audit_logger)
        before_count = audit_logger.total_entries

        asyncio.run(handler(
            {"agent_id": "rogue-agent", "tool_name": "deploy_full", "session_id": "x", "payload": {}},
            context=None,
        ))

        assert audit_logger.total_entries == before_count + 1
        last = audit_logger.get_recent(1)[0]
        assert last["authorized"] is False