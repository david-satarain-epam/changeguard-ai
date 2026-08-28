from __future__ import annotations

from typing import Any

from .tools.analyze_pr import analyze_pr


def analyze_pull_request(pr_id: str | int) -> dict[str, Any]:
    return analyze_pr(pr_id)
