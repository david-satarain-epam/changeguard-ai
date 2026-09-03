"""
Tool: deploy_full
Promotes canary to 100% traffic.
"""

import asyncio
import logging
import os

logger = logging.getLogger("changeguard-cicd.deploy_full")

async def deploy_full_handler(service: str, mode: str = "simulated", pr_id: str = "unknown") -> dict:
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

    from tools.run_tests import dispatch_github_workflow
    return await dispatch_github_workflow("deploy_full", {"service": service}, pr_id)


async def _deploy_full_live(service: str) -> dict:
    """Promote canary revision to 100% traffic."""
    google_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    google_region = os.getenv("GOOGLE_CLOUD_REGION")
    if not google_project or not google_region:
        logger.error("GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_REGION are required for live deployment")
        return await deploy_full_handler(service, "simulated")

    try:
        from google.cloud.run_v2 import ServicesClient
        from google.cloud.run_v2.types import TrafficTarget

        client = ServicesClient()
        service_path = f"projects/{google_project}/locations/{google_region}/services/{service}"

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