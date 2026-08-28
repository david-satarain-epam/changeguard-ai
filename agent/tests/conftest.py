"""
Shared fixtures for ChangeGuard AI Agent tests.
Loads all PR mock payloads for scenario testing.
"""

import json
import pytest
from pathlib import Path

MOCKS_DIR = Path(__file__).parent.parent / "pr_mocks"

# ── Individual PR fixtures ──
@pytest.fixture
def pr_847():
    with open(MOCKS_DIR / "pr-847.json") as f:
        return json.load(f)

@pytest.fixture
def pr_848():
    with open(MOCKS_DIR / "pr-848.json") as f:
        return json.load(f)

@pytest.fixture
def pr_849():
    with open(MOCKS_DIR / "pr-849.json") as f:
        return json.load(f)

@pytest.fixture
def pr_850():
    with open(MOCKS_DIR / "pr-850.json") as f:
        return json.load(f)

@pytest.fixture
def pr_851():
    with open(MOCKS_DIR / "pr-851.json") as f:
        return json.load(f)

@pytest.fixture
def pr_852():
    with open(MOCKS_DIR / "pr-852.json") as f:
        return json.load(f)

# ── All PRs fixture ──
@pytest.fixture
def all_prs():
    """Return all 6 PR mocks as a dict."""
    prs = {}
    for pr_id in ["847", "848", "849", "850", "851", "852"]:
        path = MOCKS_DIR / f"pr-{pr_id}.json"
        with open(path) as f:
            prs[pr_id] = json.load(f)
    return prs