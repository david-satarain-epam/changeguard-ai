"""Tests for Audit Logger."""


class TestAuditLogger:

    def test_logs_authorized_call(self, audit_logger):
        audit_logger.log(
            agent_id="change-impact-agent",
            tool_name="run_tests",
            session_id="pr-847",
            authorized=True,
            jit_credential_issued=True,
            action="FORWARDED",
        )
        entries = audit_logger.get_recent(1)
        assert len(entries) == 1
        assert entries[0]["authorized"] is True
        assert entries[0]["action_taken"] == "FORWARDED"

    def test_logs_blocked_call(self, audit_logger):
        audit_logger.log(
            agent_id="rogue-agent",
            tool_name="deploy_full",
            session_id="unknown",
            authorized=False,
            reason="Agent is blocked",
            action="BLOCKED",
        )
        entries = audit_logger.get_recent(1)
        assert entries[0]["authorized"] is False
        assert entries[0]["action_taken"] == "BLOCKED"

    def test_audit_id_increments(self, audit_logger):
        id1 = audit_logger.log("agent-a", "tool-1", "s1", True, action="FORWARDED")
        id2 = audit_logger.log("agent-b", "tool-2", "s2", True, action="FORWARDED")
        assert id1 == "call-0001"
        assert id2 == "call-0002"

    def test_get_recent_respects_limit(self, audit_logger):
        for i in range(30):
            audit_logger.log(f"agent-{i}", "run_tests", f"s-{i}", True)
        entries = audit_logger.get_recent(10)
        assert len(entries) == 10

    def test_total_entries(self, audit_logger):
        for i in range(5):
            audit_logger.log(f"agent-{i}", "run_tests", f"s-{i}", True)
        assert audit_logger.total_entries == 5

    def test_entry_has_timestamp(self, audit_logger):
        audit_logger.log("agent", "tool", "session", True)
        entry = audit_logger.get_recent(1)[0]
        assert "timestamp" in entry