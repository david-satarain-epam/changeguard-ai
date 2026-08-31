"""Tools for GitHub PR Risk Assessment."""

import os
import re
import json
import urllib.request

# ─── Risk Configuration ──────────────────────────────────────────

RISK_NAMES   = {0: "LOW", 1: "MEDIUM", 2: "HIGH", 3: "CRITICAL"}
DECISION_MAP = {
    0: ("APPROVE",  "DIRECT"),
    1: ("APPROVE",  "GATED"),
    2: ("ROLLOUT",  "CANARY"),
    3: ("POSTPONE", "NONE"),
}

SERVICE_KEYWORDS = {
    "auth-service":         ["auth", "authentication", "login", "oauth", "token",
                             "credential", "sso", "mfa", "jwt", "multi-factor", "multifactor"],
    "payment-api":          ["payment", "billing", "invoice", "stripe", "refund",
                             "charge", "transaction", "checkout"],
    "user-service":         ["user", "profile", "account", "registration", "signup", "onboarding"],
    "notification-service": ["notification", "email", "sms", "push", "alert", "webhook"],
    "caching-service":      ["cache", "caching", "redis", "memcache"],
    "api-gateway":          ["gateway", "routing", "proxy", "rate limit", "throttle"],
}

SERVICE_CONSUMERS = {
    "auth-service":         5000000,
    "payment-api":          12,
    "user-service":         50000,
    "notification-service": 2,
    "caching-service":      10,
    "api-gateway":          100000,
    "main-app-repo":        0,
}

SERVICE_TIERS = {
    "auth-service":         1,
    "payment-api":          1,
    "user-service":         2,
    "caching-service":      3,
    "notification-service": 3,
    "api-gateway":          2,
    "main-app-repo":        3,
}

HIGH_RISK_KW = [
    "auth", "authentication", "payment", "security", "credential",
    "breaking", "schema", "migration", "mfa", "multifactor",
    "multi-factor", "critical", "hotfix", "checkout",
]
MEDIUM_RISK_KW = [
    "caching", "config", "database", "api", "endpoint", "refactor",
    "gateway", "proxy", "performance", "cache", "redis",
]
BREAKING_KW = [
    "breaking change", "breaking:", "[breaking]", "schema change",
    "type changed", "incompatible", "deprecate",
]

TEST_PLANS = {
    "auth-service": [
        "Execute full QA regression suite",
        "Conduct penetration testing on the staging environment",
        "Perform security and architectural review by senior engineers",
    ],
    "payment-api": [
        "Run full CI/CD pipeline including unit and integration tests",
        "Run contract tests for payment schema",
    ],
    "user-service": [
        "Run unit and integration tests",
        "Verify user data consistency on staging",
    ],
    "notification-service": [
        "Run unit tests",
        "Verify notification delivery on staging",
    ],
    "caching-service": [
        "Run unit and integration tests",
        "Manual QA on staging to verify cache invalidation and data consistency",
    ],
    "api-gateway": [
        "Run integration tests",
        "Verify routing and rate limiting behavior",
    ],
    "main-app-repo": [
        "Run Build Verification",
        "Run Linter/Static Analysis",
    ],
}


# ─── GitHub API ──────────────────────────────────────────────────

def parse_repo_url(repo_url: str) -> tuple:
    """Extract (owner, repo) from a GitHub URL or 'owner/repo' string."""
    url = repo_url.strip().rstrip("/")
    match = re.match(r"https?://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?$", url)
    if match:
        return match.group(1), match.group(2)
    match = re.match(r"^([^/\s]+)/([^/\s]+)$", url)
    if match:
        return match.group(1), match.group(2)
    return None, None


def fetch_github_prs(repo_url: str) -> dict:
    """Fetch up to 10 most recent open PRs from a public GitHub repository."""
    owner, repo = parse_repo_url(repo_url)

    if not owner:
        print(f"Warning: cannot parse repo URL '{repo_url}'. Using mock data.")
        return get_mock_prs(repo_url)

    api_url = (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/pulls?state=open&per_page=10&sort=created&direction=desc"
    )
    headers = {
        "User-Agent": "ChangeGuard-AI-Agent",
        "Accept":     "application/vnd.github.v3+json",
    }
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            prs_data = json.loads(resp.read().decode())

        if not prs_data:
            print("No open PRs found. Using mock data.")
            return get_mock_prs(repo_url)

        prs = [
            {
                "pr_id":       str(pr["number"]),
                "pr_title":    pr.get("title", "Untitled PR"),
                "description": pr.get("body", "") or "",
                "pr_url":      pr.get("html_url", ""),
            }
            for pr in prs_data[:10]
        ]
        return {"repo_url": repo_url, "repo_owner": owner, "repo_name": repo, "prs": prs}

    except Exception as exc:
        print(f"Warning: GitHub API error ({exc}). Using mock data.")
        return get_mock_prs(repo_url)


def get_mock_prs(repo_url: str = "https://github.com/example/demo-repo") -> dict:
    """Return a realistic mock PR list used when the API is unavailable."""
    base = repo_url.rstrip("/")
    return {
        "repo_url":   repo_url,
        "repo_owner": "example",
        "repo_name":  "demo-repo",
        "prs": [
            {
                "pr_id":       "735",
                "pr_title":    "Add comments to the payment processing module",
                "description": "Added documentation comments to improve code readability. No functional changes.",
                "pr_url":      f"{base}/pull/735",
            },
            {
                "pr_id":       "801",
                "pr_title":    "Add caching layer for user profile service",
                "description": "Introduces Redis caching for user profile lookups. Adds new dependency on caching-service. New endpoint for cache invalidation.",
                "pr_url":      f"{base}/pull/801",
            },
            {
                "pr_id":       "620",
                "pr_title":    "Refactor authentication flow to support multi-factor authentication",
                "description": "Significant architectural change to auth-service. Affects all dependent services. Breaking change to token validation API.",
                "pr_url":      f"{base}/pull/620",
            },
            {
                "pr_id":       "812",
                "pr_title":    "Hotfix for P0 Production Incident in payment gateway",
                "description": "Critical hotfix for payment gateway connector. Breaking change to payment schema. Requires immediate deployment review.",
                "pr_url":      f"{base}/pull/812",
            },
        ],
    }


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


# ─── Pipeline Simulation ─────────────────────────────────────────

def simulate_pipeline(assessment: dict) -> dict:
    """Simulate CI/CD pipeline stages branched by deployment strategy."""
    strategy   = assessment.get("deployment_strategy", "DIRECT")
    test_count = 42

    test_suite = {
        "name": "test_suite", "status": "PASSED", "duration_seconds": 47,
        "details": f"{test_count}/{test_count} tests passed",
        "tests": {"total": test_count, "passed": test_count, "failed": 0, "skipped": 0},
    }
    security_scan = {
        "name": "security_scan", "status": "PASSED", "duration_seconds": 25,
        "details": "0 vulnerabilities found",
    }
    manual_approval = {
        "name": "manual_approval", "status": "APPROVED", "duration_seconds": 0,
        "details": "Manual approval granted by reviewer",
    }
    deploy_canary = {
        "name": "deploy_canary", "status": "COMPLETED", "duration_seconds": 20,
        "details": "Canary deployed at 10% traffic", "traffic_routed_pct": 10,
    }
    monitoring = {
        "name": "monitoring", "status": "COMPLETED", "duration_seconds": 20,
        "details": "All metrics within thresholds",
        "metrics": {
            "error_rate_pct":           0.01,
            "error_rate_threshold_pct": 1.0,
            "latency_p95_ms":           120,
            "latency_threshold_ms":     500,
            "throughput_rps":           850,
            "status":                   "HEALTHY",
        },
    }
    deploy_full = {
        "name": "deploy_full", "status": "COMPLETED", "duration_seconds": 30,
        "details": "100% traffic routed", "traffic_routed_pct": 100,
    }

    if strategy == "DIRECT":
        stages   = [test_suite, security_scan, deploy_full]
        duration = 47 + 25 + 30
    elif strategy == "GATED":
        stages   = [test_suite, security_scan, manual_approval, deploy_full]
        duration = 47 + 25 + 0 + 30
    elif strategy == "CANARY":
        stages   = [test_suite, security_scan, deploy_canary, monitoring, deploy_full]
        duration = 47 + 25 + 20 + 20 + 30
    else:  # NONE / POSTPONE
        stages   = []
        duration = 0

    return {
        "stages":                 stages,
        "final_status":          "POSTPONED" if strategy == "NONE" else "SUCCESS",
        "total_duration_seconds": duration,
    }
