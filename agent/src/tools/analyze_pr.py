from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MOCKS_DIR = Path(__file__).parent.parent / "data" / "pr-mocks"


def analyze_pr(pr_id: str | int) -> dict[str, Any]:
    """Analyze a pull request mock and return the shared agent contract."""
    normalized_id = str(pr_id).removeprefix("pr-")
    mock_path = MOCKS_DIR / f"pr-{normalized_id}.json"

    if not mock_path.exists():
        raise FileNotFoundError(f"No mock found for PR {pr_id}")

    mock = json.loads(mock_path.read_text(encoding="utf-8"))
    changed_files = mock.get("changedFiles", [])
    return {
        "pr_id": str(mock.get("number", normalized_id)),
        "risk_score": "LOW",
        "decision": "APPROVE",
        "affected_services": changed_files,
        "affected_consumers_count": len(changed_files),
        "test_plan": [],
        "suggested_new_tests": [],
        "coverage_gap_detected": False,
        "deployment_strategy": "DIRECT",
        "reasoning": "Initial mock analysis completed.",
    }
