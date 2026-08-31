"""
Context tools — Call the Impact Context MCP Server.

These retrieve business context that the agent uses for risk assessment.
In Layer 1 (standalone), they return mock data.
In Layer 2 (connected), they call the Impact Context Server via MCP.
"""

import logging
import os
from google.adk.tools import FunctionTool, ToolContext

logger = logging.getLogger("changeguard-agent.context")

LAYER_MODE = os.getenv("LAYER_MODE", "mock")

# ═══════════════════════════════════════════════════════════════
# compare_api_contracts
# ═══════════════════════════════════════════════════════════════

async def compare_api_contracts_handler(params: dict, context: ToolContext) -> dict:
    """
    Compare API contract versions. Returns breaking changes.
    Layer 1: mock data. Layer 2: MCP call to Impact Context Server.
    """
    if LAYER_MODE == "live":
        logger.info("Delegating compare_api_contracts to Secure Broker...")
        broker_response = await context.call_tool(
            "secure-broker",
            "authorize_tool_call",
            {"agent_id": context.agent_info.id, "tool_name": "compare_api_contracts", "session_id": params.get("pr_id", "context"), "payload": params},
        )
        return broker_response.get("forward_result") or broker_response

    service = params.get("service", "")

    logger.info("compare_api_contracts: %s", service)

    # Layer 1 — Mock
    if "payment" in service.lower():
        return {
            "has_breaking_change": True,
            "breaking_changes": [
                {"type": "TYPE_CHANGED", "path": "RefundRequest.amount",
                 "detail": "Type changed from integer to decimal"},
            ],
            "new_fields": [
                {"type": "ADDED", "path": "RefundRequest.partial_refund_amount",
                 "detail": "New optional field added"},
            ],
            "total_changes": 2,
            "service": service,
        }

    return {
        "has_breaking_change": False,
        "breaking_changes": [],
        "new_fields": [],
        "total_changes": 0,
        "service": service,
    }


compare_api_contracts_tool = FunctionTool(func=compare_api_contracts_handler)


# ═══════════════════════════════════════════════════════════════
# find_affected_consumers
# ═══════════════════════════════════════════════════════════════

async def find_affected_consumers_handler(params: dict, context: ToolContext) -> dict:
    """Find consumers of a service."""
    if LAYER_MODE == "live":
        logger.info("Delegating find_affected_consumers to Secure Broker...")
        broker_response = await context.call_tool(
            "secure-broker",
            "authorize_tool_call",
            {"agent_id": context.agent_info.id, "tool_name": "find_affected_consumers", "session_id": params.get("pr_id", "context"), "payload": params},
        )
        return broker_response.get("forward_result") or broker_response

    service = params.get("service", "")

    logger.info("find_affected_consumers: %s", service)

    consumers_map = {
        "payment-api": {
            "internal": ["checkout-web", "mobile-app", "merchant-portal",
                         "billing-service", "notification-service"],
            "external": ["7 clients via API Gateway"],
            "total": 12,
        },
        "auth-service": {
            "internal": ["all-services", "checkout-web", "mobile-app", "admin-panel"],
            "external": [],
            "total": 4,
        },
        "notification-service": {
            "internal": ["checkout-web", "mobile-app"],
            "external": [],
            "total": 2,
        },
    }

    result = consumers_map.get(service, {"internal": [], "external": [], "total": 0})
    result["service"] = service
    return result


find_affected_consumers_tool = FunctionTool(func=find_affected_consumers_handler)


# ═══════════════════════════════════════════════════════════════
# get_business_criticality
# ═══════════════════════════════════════════════════════════════

async def get_business_criticality_handler(params: dict, context: ToolContext) -> dict:
    """Get TIER and criticality for a service."""
    if LAYER_MODE == "live":
        logger.info("Delegating get_business_criticality to Secure Broker...")
        broker_response = await context.call_tool(
            "secure-broker",
            "authorize_tool_call",
            {"agent_id": context.agent_info.id, "tool_name": "get_business_criticality", "session_id": params.get("pr_id", "context"), "payload": params},
        )
        return broker_response.get("forward_result") or broker_response

    service = params.get("service", "")

    logger.info("get_business_criticality: %s", service)

    criticality_map = {
        "payment-api": {
            "tier": 1,
            "business_function": "Core payment processing",
            "max_downtime_minutes": 0,
            "deployment_window": "Sunday 02:00-06:00 UTC",
        },
        "auth-service": {
            "tier": 1,
            "business_function": "Authentication & SSO",
            "max_downtime_minutes": 0,
            "deployment_window": "Sunday 02:00-06:00 UTC",
        },
        "billing-service": {
            "tier": 2,
            "business_function": "Invoice management",
            "max_downtime_minutes": 240,
            "deployment_window": "Weekdays 22:00-04:00 UTC",
        },
        "notification-service": {
            "tier": 3,
            "business_function": "Email & push notifications",
            "max_downtime_minutes": 30,
            "deployment_window": "Any time",
        },
    }

    result = criticality_map.get(service, {
        "tier": 3,
        "business_function": "Unknown",
        "max_downtime_minutes": 60,
        "deployment_window": "Any time",
    })
    result["service"] = service
    return result


get_business_criticality_tool = FunctionTool(func=get_business_criticality_handler)


# ═══════════════════════════════════════════════════════════════
# get_test_catalog
# ═══════════════════════════════════════════════════════════════

async def get_test_catalog_handler(params: dict, context: ToolContext) -> dict:
    """
    Get test counts for a service.
    Returns 0 for new endpoints → triggers CRITICAL + POSTPONE.
    """
    if LAYER_MODE == "live":
        logger.info("Delegating get_test_catalog to Secure Broker...")
        broker_response = await context.call_tool(
            "secure-broker",
            "authorize_tool_call",
            {"agent_id": context.agent_info.id, "tool_name": "get_test_catalog", "session_id": params.get("pr_id", "context"), "payload": params},
        )
        return broker_response.get("forward_result") or broker_response

    service = params.get("service", "")
    affected_area = params.get("affected_area", "")

    logger.info("get_test_catalog: %s (area: %s)", service, affected_area)

    # Check for new endpoints
    if any(kw in affected_area.lower() for kw in ["batch", "new"]):
        return {
            "service": service,
            "affected_area": affected_area,
            "unit": 0, "integration": 0, "contract": 0,
            "e2e": 0, "total": 0,
            "coverage_gap": True,
            "message": "ZERO test coverage — new endpoint",
        }

    catalog = {
        "payment-api": {
            "unit": 12, "integration": 8, "contract": 6,
            "e2e": 4, "chaos": 2, "regression": 10, "smoke": 2,
            "total": 42,
        },
        "auth-service": {
            "unit": 20, "integration": 10, "contract": 4,
            "e2e": 6, "chaos": 1, "regression": 15, "smoke": 2,
            "total": 56,
        },
        "notification-service": {
            "unit": 8, "integration": 4, "contract": 2,
            "e2e": 2, "smoke": 1,
            "total": 17,
        },
    }

    result = catalog.get(service, {"total": 0, "coverage_gap": True})
    result["service"] = service
    result["affected_area"] = affected_area
    return result


get_test_catalog_tool = FunctionTool(func=get_test_catalog_handler)