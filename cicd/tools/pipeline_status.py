"""
Tool: pipeline_status
Returns current pipeline state.
"""

import logging

logger = logging.getLogger("changeguard-cicd.pipeline_status")


async def pipeline_status_handler(pipeline_id: str) -> dict:
    logger.info("pipeline_status: %s", pipeline_id)

    return {
        "pipeline_id": pipeline_id,
        "strategy": "CANARY",
        "stages": [
            {"name": "test_suite", "status": "PASSED", "duration_seconds": 47, "details": "42/42 passed"},
            {"name": "security_scan", "status": "PASSED", "duration_seconds": 25, "details": "0 vulnerabilities"},
            {"name": "deploy_canary", "status": "RUNNING", "details": "10% traffic"},
            {"name": "monitor", "status": "PENDING"},
            {"name": "deploy_full", "status": "PENDING"},
        ],
        "final_status": "IN_PROGRESS",
    }