"""
Tool: monitor
Monitors canary metrics.
Simulated: healthy metrics (or degraded if error_rate override).
Live: Cloud Monitoring API.
"""

import asyncio
import logging
import os

logger = logging.getLogger("changeguard-cicd.monitor")

async def monitor_handler(duration_minutes: int, service: str, mode: str = "simulated",
                          simulated_error_rate: float = None, pr_id: str = "unknown") -> dict:
    logger.info("monitor: %s | %d min | mode: %s", service, duration_minutes, mode)

    if mode == "simulated":
        await asyncio.sleep(2)
        error_rate = simulated_error_rate if simulated_error_rate is not None else 0.01
        is_healthy = error_rate <= 1.0

        return {
            "error_rate_pct": error_rate,
            "error_rate_threshold_pct": 1.0,
            "latency_p95_ms": 120 if is_healthy else 850,
            "latency_threshold_ms": 500,
            "throughput_rps": 850,
            "status": "HEALTHY" if is_healthy else "DEGRADED",
            "duration_minutes": duration_minutes,
            "service": service,
            "mode": "simulated",
        }

    from tools.run_tests import dispatch_github_workflow
    return await dispatch_github_workflow(
        "monitor", {"duration_minutes": str(duration_minutes), "service": service}, pr_id
    )


async def _monitor_live(duration_minutes: int, service: str) -> dict:
    """Query Cloud Monitoring for real metrics."""
    google_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not google_project:
        logger.error("GOOGLE_CLOUD_PROJECT is required for live monitoring")
        return await monitor_handler(duration_minutes, service, "simulated")

    try:
        from google.cloud import monitoring_v3
        from google.protobuf.duration_pb2 import Duration

        client = monitoring_v3.MetricServiceClient()
        project_path = f"projects/{google_project}"

        # Error rate: 5xx responses / total requests
        interval = monitoring_v3.TimeInterval()
        interval.end_time.seconds = int(asyncio.get_event_loop().time())
        interval.start_time.seconds = interval.end_time.seconds - (duration_minutes * 60)

        # Query error rate
        error_request = {
            "name": project_path,
            "filter": (
                f'metric.type="run.googleapis.com/request_count" '
                f'AND resource.labels.service_name="{service}" '
                f'AND metric.labels.response_code_class="5xx"'
            ),
            "interval": interval,
            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
        }

        error_response = client.list_time_series(request=error_request)
        error_count = sum(
            point.value.int64_value
            for ts in error_response
            for point in ts.points
        )

        # Query total requests
        total_request = dict(error_request)
        total_request["filter"] = (
            f'metric.type="run.googleapis.com/request_count" '
            f'AND resource.labels.service_name="{service}"'
        )

        total_response = client.list_time_series(request=total_request)
        total_count = sum(
            point.value.int64_value
            for ts in total_response
            for point in ts.points
        )

        error_rate = (error_count / total_count * 100) if total_count > 0 else 0
        is_healthy = error_rate <= 1.0

        return {
            "error_rate_pct": round(error_rate, 2),
            "error_rate_threshold_pct": 1.0,
            "latency_p95_ms": 0,
            "latency_threshold_ms": 500,
            "throughput_rps": total_count // (duration_minutes * 60) if duration_minutes > 0 else 0,
            "status": "HEALTHY" if is_healthy else "DEGRADED",
            "duration_minutes": duration_minutes,
            "service": service,
            "mode": "live",
        }

    except Exception as e:
        logger.error("Cloud Monitoring query failed: %s", e)
        return {
            "error_rate_pct": 0,
            "latency_p95_ms": 0,
            "throughput_rps": 0,
            "status": "UNKNOWN",
            "duration_minutes": duration_minutes,
            "service": service,
            "mode": "live",
            "error": str(e)[:200],
        }