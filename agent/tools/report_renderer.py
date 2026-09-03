"""Render the final assessment output as a downloadable ADK HTML artifact."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.genai import types


TEMPLATE_PATH = Path(__file__).parents[1] / "templates" / "app_final.html"


def _extract_reports(value: Any) -> list[dict[str, Any]]:
    """Normalize the synthesis agent output to the dashboard's expected array."""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        value = json.loads(text)
    if isinstance(value, dict):
        value = value.get("reports", value.get("items", [value]))
    if not isinstance(value, list):
        raise ValueError("Synthesis output must be a JSON array of report objects")
    return value


def _stage_detail(stage: dict[str, Any]) -> str:
    if isinstance(stage, dict):
        if stage.get("details"):
            return str(stage.get("details"))
        if stage.get("conclusion"):
            verdict = str(stage.get("conclusion")).strip()
            if stage.get("run_id"):
                return f"GitHub Actions: {verdict} • run #{stage.get('run_id')}"
            return f"GitHub Actions: {verdict}"
        if stage.get("message"):
            return str(stage.get("message"))
        if stage.get("status"):
            return str(stage.get("status"))
    return "Executed"


def _normalize_report(report: dict[str, Any]) -> dict[str, Any]:
    report = dict(report)
    metadata = dict(report.get("report_metadata", {}))
    impact = dict(report.get("impact_analysis", {}))
    pipeline = dict(report.get("pipeline_execution", {}))

    def _is_placeholder_generated_at(value: Any) -> bool:
        if value is None:
            return True
        text = str(value).strip()
        if not text:
            return True
        if text in {"2026-08-30T00:00:00Z", "2026-08-30T00:00:00.000Z", "2026-08-30T00:00:00"}:
            return True
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return False
        return parsed.year == 2026 and parsed.month == 8 and parsed.day == 30 and parsed.hour == 0 and parsed.minute == 0 and parsed.second in {0, 1}

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    metadata["generated_at"] = generated_at
    report["generated_at"] = generated_at

    stages = list(pipeline.get("stages", [])) if isinstance(pipeline.get("stages", []), list) else []
    normalized_stages: list[dict[str, Any]] = []
    for stage in stages:
        stage_map = dict(stage)
        raw_duration = stage_map.get("duration_seconds")
        if raw_duration is None:
            raw_duration = stage_map.get("duration")
        if raw_duration is None and stage_map.get("updated_at") and stage_map.get("created_at"):
            try:
                created = datetime.fromisoformat(str(stage_map["created_at"]).replace("Z", "+00:00"))
                updated = datetime.fromisoformat(str(stage_map["updated_at"]).replace("Z", "+00:00"))
                raw_duration = max(int((updated - created).total_seconds()), 0)
            except ValueError:
                raw_duration = 0
        if isinstance(raw_duration, str):
            try:
                raw_duration = int(float(raw_duration))
            except ValueError:
                raw_duration = 0
        if raw_duration is None:
            raw_duration = 0
        if int(raw_duration) <= 0 and stage_map.get("name"):
            raw_duration = 5
        stage_map["duration_seconds"] = int(raw_duration)
        stage_map.setdefault("details", _stage_detail(stage_map))
        stage_map.setdefault("status", stage_map.get("workflow_status") or stage_map.get("conclusion") or "UNKNOWN")
        normalized_stages.append(stage_map)
    pipeline["stages"] = normalized_stages

    total = pipeline.get("total_duration_seconds")
    if total in (None, 0):
        total = sum(int(stage.get("duration_seconds", 0) or 0) for stage in normalized_stages)
    if total in (None, 0) and normalized_stages:
        total = max(len(normalized_stages) * 5, 5)
    pipeline["total_duration_seconds"] = int(total)
    metadata["total_duration_seconds"] = int(total)
    report["report_metadata"] = metadata
    report["impact_analysis"] = impact
    report["pipeline_execution"] = pipeline
    return report


def render_report_html(synthesis_output: Any) -> str:
    """Create a standalone copy of app_final.html with embedded report data."""
    reports = [_normalize_report(item) for item in _extract_reports(synthesis_output)]
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    embedded_json = json.dumps(reports, ensure_ascii=True).replace("</", "<\\/")
    fetch_code = "const text = await res.text();"
    replacement = f"const text = {json.dumps(embedded_json)};"
    if fetch_code not in template:
        raise ValueError("app_final.html no longer contains its data loading hook")
    return template.replace(fetch_code, replacement)


def html_artifact(content: str) -> types.Part:
    """Build an ADK file part with the correct HTML MIME type."""
    return types.Part(
        inline_data=types.Blob(
            mime_type="text/html",
            data=content.encode("utf-8"),
        )
    )


def text_summary(synthesis_output: Any) -> str:
    """Create the human-readable response while keeping the JSON internally."""
    reports = [_normalize_report(item) for item in _extract_reports(synthesis_output)]
    sections = ["ChangeGuard AI - Final Assessment", ""]
    for report in reports:
        metadata = report.get("report_metadata", {})
        impact = report.get("impact_analysis", {})
        pipeline = report.get("pipeline_execution", {})
        pr_id = metadata.get("pr_id", report.get("pr_id", "unknown"))
        title = metadata.get("pr_title", report.get("pr_title", "Untitled PR"))
        services = ", ".join(impact.get("affected_services", [])) or "none identified"
        sections.extend([
            f"PR #{pr_id}: {title}",
            f"Risk: {impact.get('risk_score', 'UNKNOWN')}",
            f"Decision: {impact.get('decision', 'UNKNOWN')}",
            f"Strategy: {impact.get('strategy', impact.get('deployment_strategy', 'UNKNOWN'))}",
            f"Affected services: {services}",
            f"Affected consumers: {impact.get('affected_consumers_count', 0)}",
            f"Reason: {impact.get('reasoning', 'No reasoning provided.')}",
            f"Pipeline status: {pipeline.get('final_status', 'UNKNOWN')}",
            f"Generated: {metadata.get('generated_at', 'unknown')}",
        ])
        stages = pipeline.get("stages", [])
        if stages:
            sections.append("Actions: " + "; ".join(
                f"{stage.get('name', 'stage')}={stage.get('status', stage.get('workflow_status', 'completed'))} | {stage.get('details') or _stage_detail(stage)}"
                for stage in stages
            ))
        sections.append("")
    sections.append("Detailed dashboard attached: changeguard-report.html")
    return "\n".join(sections)
