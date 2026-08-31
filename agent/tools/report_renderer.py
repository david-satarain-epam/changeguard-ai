"""Render the final assessment output as a downloadable ADK HTML artifact."""

import json
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


def render_report_html(synthesis_output: Any) -> str:
    """Create a standalone copy of app_final.html with embedded report data."""
    reports = _extract_reports(synthesis_output)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    embedded_json = json.dumps(reports, ensure_ascii=True).replace("</", "<\\/")
    fetch_code = "const text = await res.text();"
    replacement = f"const text = {json.dumps(embedded_json)};"
    if fetch_code not in template:
        raise ValueError("app_final.html no longer contains its data loading hook")
    return template.replace(fetch_code, replacement).replace(
        "const res = await fetch('../contracts/agent_output.json');",
        "const res = { ok: true, status: 200 };",
    )


def html_artifact(content: str) -> types.Part:
    """Build an ADK file part with the correct HTML MIME type."""
    return types.Part(
        inline_data=types.Blob(
            mime_type="text/html",
            data=content.encode("utf-8"),
        )
    )
