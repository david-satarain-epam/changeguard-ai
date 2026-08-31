"""
Tool: deploy_canary
Deploys a canary revision to a percentage of traffic.
"""

import asyncio
import logging
import os

logger = logging.getLogger("changeguard-cicd.deploy_canary")

GOOGLE_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_REGION = os.getenv("GOOGLE_CLOUD_REGION", "us-east1")


async def deploy_canary_handler(percentage: int, service: str, mode: str = "simulated") -> dict:
    logger.info("deploy_canary: %d%% | %s | mode: %s", percentage, service, mode)

    if mode == "simulated":
        await asyncio.sleep(1)
        return {
            "status": "RUNNING",
            "traffic_routed_pct": percentage,
            "service": service,
            "duration_seconds": 20,
            "message": f"Canary deployed at {percentage}% traffic — metrics nominal",
            "mode": "simulated",
        }

    # ── Live mode: Cloud Run traffic splitting ──
    return await _deploy_canary_live(percentage, service)


async def _deploy_canary_live(percentage: int, service: str) -> dict:
    """Update Cloud Run traffic to split between canary and stable."""
    if not GOOGLE_PROJECT:
        logger.warning("GOOGLE_CLOUD_PROJECT not set — falling back to simulated")
        return await deploy_canary_handler(percentage, service, "simulated")

    try:
        from google.cloud.run_v2 import ServicesClient
        from google.cloud.run_v2.types import TrafficTarget, RevisionTrafficTarget

        client = ServicesClient()
        service_path = f"projects/{GOOGLE_PROJECT}/locations/{GOOGLE_REGION}/services/{service}"

        # Get current service
        current = client.get_service(name=service_path)

        # Configure traffic: canary gets `percentage`, latest gets the rest
        new_traffic = [
            TrafficTarget(
                type_=TrafficTarget.TrafficTargetType.TRAFFIC_TARGET_TYPE_REVISION,
                revision="latest",
                percent=100 - percentage,
                tag="stable",
            ),
            TrafficTarget(
                type_=TrafficTarget.TrafficTargetType.TRAFFIC_TARGET_TYPE_REVISION,
                revision="latest",
                percent=percentage,
                tag="canary",
            ),
        ]

        current.traffic.clear()
        current.traffic.extend(new_traffic)

        client.update_service(service=current)

        return {
            "status": "RUNNING",
            "traffic_routed_pct": percentage,
            "service": service,
            "message": f"Cloud Run traffic updated — {percentage}% canary",
            "mode": "live",
        }

    except Exception as e:
        logger.error("Cloud Run deploy failed: %s", e)
        return {
            "status": "FAILED",
            "traffic_routed_pct": 0,
            "service": service,
            "message": f"Cloud Run error: {str(e)[:200]}",
            "mode": "live",
        }