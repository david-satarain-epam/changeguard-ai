"""
Tool: rollback
Emergency rollback to previous stable revision.
"""

import asyncio
import logging
import os

logger = logging.getLogger("changeguard-cicd.rollback")

GOOGLE_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_REGION = os.getenv("GOOGLE_CLOUD_REGION", "us-east1")


async def rollback_handler(service: str, rollback_version: str = "previous",
                           mode: str = "simulated") -> dict:
    logger.warning("rollback: %s → %s | mode: %s", service, rollback_version, mode)

    if mode == "simulated":
        await asyncio.sleep(1)
        return {
            "status": "ROLLED_BACK",
            "traffic_restored_pct": 100,
            "service": service,
            "rollback_version": rollback_version,
            "duration_seconds": 10,
            "message": f"Rollback complete — traffic restored to {rollback_version}",
            "mode": "simulated",
        }

    return await _rollback_live(service, rollback_version)


async def _rollback_live(service: str, rollback_version: str) -> dict:
    """Restore previous revision to 100% traffic."""
    if not GOOGLE_PROJECT:
        logger.warning("GOOGLE_CLOUD_PROJECT not set — falling back to simulated")
        return await rollback_handler(service, rollback_version, "simulated")

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
                revision=rollback_version,
                percent=100,
                tag="stable",
            )
        )

        client.update_service(service=current)

        return {
            "status": "ROLLED_BACK",
            "traffic_restored_pct": 100,
            "service": service,
            "rollback_version": rollback_version,
            "message": f"Cloud Run traffic restored — 100% to {rollback_version}",
            "mode": "live",
        }

    except Exception as e:
        logger.error("Cloud Run rollback failed: %s", e)
        return {
            "status": "FAILED",
            "traffic_restored_pct": 0,
            "service": service,
            "message": f"Cloud Run error: {str(e)[:200]}",
            "mode": "live",
        }