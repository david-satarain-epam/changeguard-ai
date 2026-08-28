from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .agent import analyze_pull_request

app = FastAPI(title="ChangeGuard AI Agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/analyze-pr/{pr_id}")
def analyze_pr_endpoint(pr_id: str) -> dict:
    try:
        return analyze_pull_request(pr_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
