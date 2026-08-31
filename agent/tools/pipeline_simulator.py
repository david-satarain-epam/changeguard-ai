# agent/tools/pipeline_simulator.py
"""CI/CD Pipeline simulation logic."""

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
