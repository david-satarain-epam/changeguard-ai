from __future__ import annotations

from fastapi import FastAPI

from services.audit_logger import AuditLogger
from tools.authorize import authorize
from tools.get_audit_log import get_audit_log

app = FastAPI(title="ChangeGuard Secure Broker")
audit_logger = AuditLogger()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/authorize")
def authorize_endpoint(tool_name: str, agent_id: str = "changeguard-agent") -> dict:
    return authorize(tool_name=tool_name, agent_id=agent_id)


@app.get("/audit-log")
def audit_log_endpoint() -> dict:
    return get_audit_log(audit_logger)
