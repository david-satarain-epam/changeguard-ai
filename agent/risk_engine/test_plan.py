"""Test plan generation."""


def generate_test_plan(affected_services: list) -> list:
    """Generate test plan based on affected services."""
    templates = {
        "payment-api": [
            "unit:test_refund_rules",
            "unit:test_schema_validation",
            "integration:test_payment_api",
            "contract:test_openapi_schema",
            "smoke:test_health",
        ],
        "auth-service": [
            "unit:test_oauth",
            "unit:test_token",
            "integration:test_auth_flow",
            "smoke:test_health",
        ],
        "notification-service": [
            "unit:test_template_rendering",
            "smoke:test_health",
        ],
        "billing-service": [
            "unit:test_invoice",
            "smoke:test_health",
        ],
    }

    plan = []
    for svc in affected_services:
        if svc in templates:
            plan.extend(templates[svc])

    return plan if plan else ["smoke:test_health"]


def generate_suggested_tests(diff_summary: str, affected_services: list) -> list:
    """Generate suggested tests for new endpoints with zero coverage."""
    if "batch" in diff_summary.lower():
        return [
            "unit:test_batch_refund_single_transaction",
            "unit:test_batch_refund_multiple_transactions",
            "unit:test_batch_refund_partial_failure",
            "unit:test_batch_refund_empty_array_validation",
            "integration:test_batch_refund_db_atomicity",
            "integration:test_batch_refund_message_queue",
            "contract:test_batch_refund_request_schema",
            "contract:test_batch_refund_response_schema",
        ]

    return [
        f"unit:test_new_endpoint_{svc.replace('-', '_')}"
        for svc in affected_services
    ]