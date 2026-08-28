from agent.agent import analyze_pull_request


def test_analyze_pull_request_uses_mock() -> None:
    result = analyze_pull_request(847)

    assert result["pr_id"] == "847"
    assert result["risk_score"] == "LOW"
    assert result["decision"] == "APPROVE"
    assert result["deployment_strategy"] == "DIRECT"
