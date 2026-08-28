from __future__ import annotations

from fastapi import FastAPI

from tools.compare_contracts import compare_contracts
from tools.find_consumers import find_consumers
from tools.get_criticality import get_criticality
from tools.get_test_catalog import get_test_catalog

app = FastAPI(title="ChangeGuard Impact Context")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/contracts/compare")
def compare_contracts_endpoint(contract: str = "") -> dict:
    return compare_contracts(contract)


@app.get("/consumers/{service}")
def find_consumers_endpoint(service: str) -> dict:
    return find_consumers(service)


@app.get("/criticality/{service}")
def get_criticality_endpoint(service: str) -> dict:
    return get_criticality(service)


@app.get("/tests/{service}")
def get_test_catalog_endpoint(service: str) -> dict:
    return get_test_catalog(service)
