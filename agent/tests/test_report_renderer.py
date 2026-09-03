from tools.report_renderer import render_report_html


def test_render_report_html_includes_runtime_stage_details_and_pdf_button() -> None:
    report = [{
        "report_metadata": {
            "pr_id": "847",
            "pr_title": "Demo PR",
            "generated_at": "2026-08-30T00:00:00Z",
            "total_duration_seconds": 90,
            "status": "SUCCESS",
        },
        "impact_analysis": {
            "risk_score": "HIGH",
            "decision": "APPROVE",
            "strategy": "DIRECT",
            "affected_services": ["payments"],
            "affected_consumers_count": 3,
            "reasoning": "This touches critical payment flows.",
            "escalation_log": ["contract change"],
            "coverage_gap_detected": True,
            "context_sources": {"files_changed": True},
        },
        "pipeline_execution": {
            "final_status": "SUCCESS",
            "total_duration_seconds": 90,
            "stages": [
                {
                    "name": "run_tests",
                    "status": "SUCCESS",
                    "duration_seconds": 30,
                    "details": "15/15 tests passed",
                },
                {
                    "name": "deploy_full",
                    "status": "SUCCESS",
                    "duration_seconds": 60,
                    "details": "GitHub Actions: success • run #123",
                },
            ],
        },
    }]

    html = render_report_html(report)

    assert "Print PDF" in html
    assert "15/15 tests passed" in html
    assert "Generated:" in html
    assert "1m 30s" in html or "90" in html
    assert "2026-08-30T00:00:00Z" not in html
