"""Public tool exports for the ChangeGuard agent."""

from .github_api import fetch_github_prs
from .risk_analyzer import calculate_pr_risk
from .pipeline_simulator import simulate_pipeline

# Backward-compatible aliases for older imports.
try:
    from .analyze_pr import fetch_github_pr
except Exception:  # pragma: no cover
    fetch_github_pr = None

__all__ = [
    "fetch_github_prs",
    "fetch_github_pr",
    "calculate_pr_risk",
    "simulate_pipeline",
]
