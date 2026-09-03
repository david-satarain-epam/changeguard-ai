"""Shared fixtures for Broker tests."""

import pytest
from pathlib import Path
from services.policy_engine import PolicyEngine
from services.jit_credentials import JitCredentialGenerator
from services.audit_logger import AuditLogger


@pytest.fixture
def policy_engine():
    """Policy engine with test policies."""
    return PolicyEngine()


@pytest.fixture
def jit_creds():
    """JIT credential generator."""
    return JitCredentialGenerator(default_ttl_minutes=15)


@pytest.fixture
def audit_logger():
    """Fresh audit logger."""
    return AuditLogger()