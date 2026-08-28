"""Service identification from changed files."""

from .rules import PATH_TO_SERVICE


def identify_affected_services(files_changed: list) -> list:
    """Map changed file paths to affected services."""
    services = set()
    for file in files_changed:
        for path, service in PATH_TO_SERVICE.items():
            if path in file:
                services.add(service)
    return sorted(services) if services else ["unknown"]


def has_schema_change(files_changed: list) -> bool:
    """Check if any changed file is a schema/contract definition."""
    keywords = ["schema", "openapi", "contract", "spec", ".json"]
    return any(
        kw in f.lower()
        for f in files_changed
        for kw in keywords
    )


def is_new_endpoint(diff_summary: str, files_changed: list) -> bool:
    """Detect if PR introduces a new endpoint (likely zero coverage)."""
    summary_kw = ["new endpoint", "new file", "batch", "zero test"]
    file_kw = ["batch_refund", "new_endpoint"]

    return (
        any(kw in diff_summary.lower() for kw in summary_kw) or
        any(any(kw in f.lower() for kw in file_kw) for f in files_changed)
    )