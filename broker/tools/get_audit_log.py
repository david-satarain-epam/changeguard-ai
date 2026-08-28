from services.audit_logger import AuditLogger


def get_audit_log(logger: AuditLogger) -> dict[str, object]:
    return {"entries": logger.entries}
