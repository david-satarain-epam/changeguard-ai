"""
Tool: deploy_full
Promotes canary to 100% traffic.
"""

import asyncio
import logging
import os

logger = logging.getLogger("changeguard-cicd.deploy_full")

GOOGLE_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_REGION = os.getenv("GOOGLE_CLOUD_REGION", "us-east1")


async def deploy_full_handler(service: str, mode: str = "simulated") -> dict:
    logger.info("deploy_full: %s | mode: %s", service, mode)

    if mode == "simulated":
        await asyncio.sleep(1)
        return {
            "status": "DEPLOYED",
            "traffic_routed_pct": 100,
            "service": service,
            "duration_seconds": 30,
            "message": "Full deployment complete — 100% traffic routed",
            "mode": "simulated",
        }

    return await _deploy_full_live(service)


async def _deploy_full_live(service: str) -> dict:
    """Promote canary revision to 100% traffic."""
    if not GOOGLE_PROJECT:
        logger.warning("GOOGLE_CLOUD_PROJECT not set — falling back to simulated")
        return await deploy_full_handler(service, "simulated")

    try:
        from google.cloud.run_v2 import ServicesClient
        from google.cloud.run_v2.types import TrafficTarget

        client = ServicesClient()
        service_path = f"projects/{GOOGLE_PROJECT}/locations/{GOOGLE_REGION}/services/{service}"

        current = client.get_service(name=service_path)

        current.traffic.clear()
        current.traffic.append(
            TrafficTarget(
                type_=TrafficTarget.TrafficTargetType.TRAFFIC_TARGET_TYPE_REVISION,
                revision="latest",
                percent=100,
                tag="stable",
            )
        )

        client.update_service(service=current)

        return {
            "status": "DEPLOYED",
            "traffic_routed_pct": 100,
            "service": service,
            "message": "Cloud Run traffic updated — 100% to stable",
            "mode": "live",
        }

    except Exception as e:
        logger.error("Cloud Run full deploy failed: %s", e)
        return {
            "status": "FAILED",
            "traffic_routed_pct": 0,
            "service": service,
            "message": f"Cloud Run error: {str(e)[:200]}",
            "mode": "live",
        }