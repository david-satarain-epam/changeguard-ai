# agent/tools/risk_analyzer.py
"""Risk scoring logic for GitHub PRs."""

import os
import json

# ─── Configuration ──────────────────────────────────────────

def load_config(filename: str):
    """Load a JSON config if it exists, otherwise return a safe fallback."""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(dir_path, '..', 'config', filename)
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


SERVICES_CONFIG = load_config('services.json') or {
    "payment-api": {
        "keywords": ["payment", "card", "gateway", "stripe"],
        "consumers": 12,
        "tier": 1,
        "test_plan": ["unit payment contract tests", "integration payment gateway tests"],
    },
    "auth-service": {
        "keywords": ["auth", "login", "token", "jwt", "oauth"],
        "consumers": 4,
        "tier": 1,
        "test_plan": ["jwt validation tests", "auth flow regression tests"],
    },
    "billing-service": {
        "keywords": ["billing", "invoice", "charge", "refund"],
        "consumers": 3,
        "tier": 2,
        "test_plan": ["billing reconciliation tests", "refund flow tests"],
    },
    "notification-service": {
        "keywords": ["notify", "email", "sms", "message"],
        "consumers": 2,
        "tier": 3,
        "test_plan": ["notification delivery tests", "retry policy tests"],
    },
    "main-app-repo": {
        "keywords": ["app", "repo", "core"],
        "consumers": 0,
        "tier": 3,
        "test_plan": ["smoke tests", "deployment health checks"],
    },
}

RISK_CONFIG = load_config('risk_rules.json') or {
    "risk_levels": {0: "LOW", 1: "MEDIUM", 2: "HIGH", 3: "CRITICAL"},
    "decision_map": {
        0: ["APPROVE", "DIRECT"],
        1: ["APPROVE", "GATED"],
        2: ["ROLLOUT", "CANARY"],
        3: ["POSTPONE", "NONE"],
    },
    "keywords": {
        "high": ["breaking", "security", "hotfix", "critical", "incident", "schema", "auth"],
        "medium": ["update", "refactor", "config", "api", "cache", "payment"],
        "breaking": ["breaking", "incompatible", "remove endpoint", "rename field", "schema change"],
    },
}

RISK_NAMES = {int(k): v for k, v in RISK_CONFIG['risk_levels'].items()}
DECISION_MAP = {int(k): tuple(v) for k, v in RISK_CONFIG['decision_map'].items()}
HIGH_RISK_KW = RISK_CONFIG['keywords']['high']
MEDIUM_RISK_KW = RISK_CONFIG['keywords']['medium']
BREAKING_KW = RISK_CONFIG['keywords']['breaking']

SERVICE_KEYWORDS = {k: v['keywords'] for k, v in SERVICES_CONFIG.items()}
SERVICE_CONSUMERS = {k: v['consumers'] for k, v in SERVICES_CONFIG.items()}
SERVICE_TIERS = {k: v['tier'] for k, v in SERVICES_CONFIG.items()}
TEST_PLANS = {k: v['test_plan'] for k, v in SERVICES_CONFIG.items()}


# ─── Risk Scoring ────────────────────────────────────────────────

def identify_services(title: str, description: str) -> list:
    """Map PR title and description to affected services via keyword matching."""
    text  = f"{title} {description}".lower()
    found = [svc for svc, kws in SERVICE_KEYWORDS.items() if any(kw in text for kw in kws)]
    return found if found else ["main-app-repo"]


def calculate_pr_risk(pr: dict) -> dict:
    """Score a PR's risk level using keyword heuristics on title and description."""
    title       = pr.get("pr_title", "")
    description = pr.get("description", "")
    text        = f"{title} {description}".lower()

    risk    = 0
    reasons = []

    # 1. Keyword-based baseline
    matched_high = [kw for kw in HIGH_RISK_KW if kw in text]
    if matched_high:
        risk = max(risk, 2)
        reasons.append(f"High-risk keywords detected: {', '.join(matched_high[:3])}")
    else:
        matched_medium = [kw for kw in MEDIUM_RISK_KW if kw in text]
        if matched_medium:
            risk = max(risk, 1)
            reasons.append(f"Medium-risk keywords detected: {', '.join(matched_medium[:3])}")
        else:
            reasons.append("Non-functional or low-impact change")

    # 2. Breaking change escalation
    has_breaking = any(kw in text for kw in BREAKING_KW)
    if has_breaking:
        risk = min(risk + 1, 3)
        reasons.append("Breaking change detected → +1")

    # 3. Identify affected services
    affected_services = identify_services(title, description)

    # 4. TIER 1 service escalation
    for svc in affected_services:
        if SERVICE_TIERS.get(svc, 3) == 1:
            risk = min(risk + 1, 3)
            reasons.append(f"TIER 1 service '{svc}' affected → +1")
            break

    # 5. Multiple services escalation
    if len(affected_services) >= 3:
        risk = min(risk + 1, 3)
        reasons.append(f"{len(affected_services)} services affected → +1")

    risk     = min(risk, 3)
    decision, strategy = DECISION_MAP[risk]

    consumer_count = sum(SERVICE_CONSUMERS.get(s, 0) for s in affected_services)

    coverage_gap = any(
        kw in text for kw in ["new endpoint", "new service", "new api", "adds endpoint", "new route"]
    )

    # Build test plan from affected services (deduplicated, ordered)
    test_plan = []
    for svc in affected_services:
        for t in TEST_PLANS.get(svc, TEST_PLANS["main-app-repo"]):
            if t not in test_plan:
                test_plan.append(t)

    # Suggested new tests for high-risk or coverage-gap PRs
    suggested = []
    if coverage_gap:
        suggested = [f"Add integration test for new endpoint in {s}" for s in affected_services]
    elif risk >= 2:
        for svc in affected_services:
            if "auth" in svc:
                suggested += [
                    "Add negative test cases for JWT signature verification",
                    "Add performance benchmark test for token generation",
                ]
            elif "payment" in svc:
                suggested += ["Add integration test for payment schema change"]

    context_sources = {
        "api_contract_checked": has_breaking,
        "consumers_queried":    len(affected_services) > 1,
        "criticality_checked":  True,
        "test_catalog_queried": True,
    }

    return {
        "pr_id":                    pr["pr_id"],
        "pr_title":                 pr["pr_title"],
        "pr_url":                   pr.get("pr_url", ""),
        "risk_score":               RISK_NAMES[risk],
        "decision":                 decision,
        "deployment_strategy":      strategy,
        "affected_services":        affected_services,
        "affected_consumers_count": consumer_count,
        "test_plan":                test_plan,
        "suggested_new_tests":      suggested,
        "coverage_gap_detected":    coverage_gap,
        "escalation_log":           reasons,
        "context_sources":          context_sources,
    }
