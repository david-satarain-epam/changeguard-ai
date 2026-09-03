"""Deterministic risk scoring."""

from .rules import RISK_LEVELS, SERVICE_TIERS, DECISION_MAP
from .services import has_schema_change


def calculate_risk_score(
    files_changed: list,
    diff_summary: str = "",
    contract_has_breaking: bool = False,
    affected_services: list = None,
    test_coverage_zero: bool = False,
) -> dict:
    """
    Calculate risk using deterministic rules.

    Returns dict with: score, level, reasons, decision, strategy
    """
    if affected_services is None:
        from .services import identify_affected_services
        affected_services = identify_affected_services(files_changed)

    risk = 0
    reasons = []

    # 1. Path-based minimum risk
    from .rules import PATH_RULES
    for file in files_changed:
        for path, min_risk, reason in PATH_RULES:
            if path in file and RISK_LEVELS[min_risk] > risk:
                risk = RISK_LEVELS[min_risk]
                reasons.append(f"Path '{path}' → minimum {min_risk} ({reason})")
                break

    # 2. Schema change
    if has_schema_change(files_changed):
        risk += 1
        reasons.append("Schema/contract file changed → +1")

    # 3. Multiple services
    if len(affected_services) >= 3:
        risk += 1
        reasons.append(f"{len(affected_services)} services affected → +1")

    # 4. TIER 1
    for svc in affected_services:
        if SERVICE_TIERS.get(svc, 3) == 1:
            risk += 1
            reasons.append(f"TIER 1 service '{svc}' affected → +1")
            break

    # 5. Breaking change
    if contract_has_breaking:
        risk += 1
        reasons.append("Breaking API contract change → +1")

    # 6. Zero coverage → CRITICAL
    if test_coverage_zero:
        risk = 3
        reasons.append("ZERO test coverage → CRITICAL")
    else:
        risk = min(risk, 2)

    risk = min(risk, 3)

    from .rules import RISK_NAMES
    decision, strategy = DECISION_MAP[risk]

    return {
        "score": RISK_NAMES[risk],
        "level": risk,
        "reasons": reasons,
        "decision": decision,
        "strategy": strategy,
    }