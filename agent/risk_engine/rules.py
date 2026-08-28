"""
Risk rules — constants and configuration.

These are the source of truth for risk scoring.
Change them here, and the agent behavior changes.
"""

RISK_LEVELS = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
RISK_NAMES  = {0: "LOW", 1: "MEDIUM", 2: "HIGH", 3: "CRITICAL"}

# Path → (minimum risk, reason)
PATH_RULES = [
    ("src/payment/",       "MEDIUM", "Core payment processing"),
    ("src/auth/",          "HIGH",   "Authentication — affects ALL services"),
    ("src/billing/",       "MEDIUM", "Revenue recognition"),
    ("src/notifications/", "LOW",    "Non-critical, async notifications"),
    ("src/utils/",         "LOW",    "Shared utility code"),
]

# File path → service name
PATH_TO_SERVICE = {
    "src/payment/":       "payment-api",
    "src/auth/":          "auth-service",
    "src/billing/":       "billing-service",
    "src/notifications/": "notification-service",
    "src/utils/":         "all-services",
}

# Service → TIER
SERVICE_TIERS = {
    "payment-api": 1,
    "auth-service": 1,
    "billing-service": 2,
    "notification-service": 3,
    "all-services": 3,
}

# Service → consumer count
SERVICE_CONSUMERS = {
    "payment-api": 12,
    "auth-service": 4,
    "billing-service": 3,
    "notification-service": 2,
    "all-services": 0,
}

# Decision mapping
DECISION_MAP = {
    0: ("APPROVE",  "DIRECT"),
    1: ("APPROVE",  "GATED"),
    2: ("ROLLOUT",  "CANARY"),
    3: ("POSTPONE", "NONE"),
}