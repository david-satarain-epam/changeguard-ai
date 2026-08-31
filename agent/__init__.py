"""ChangeGuard AI agent package."""

# Do not import the concrete agent module here; that creates a circular import when
# the ADK loader imports the package and then executes agent.py as part of the package.
# The loader should import the submodule directly when needed.
__all__ = ["agent", "input_app", "main_app"]

try:
    from . import agent as _agent_module  # pragma: no cover
    from .agent import input_app, main_app  # pragma: no cover
except Exception:  # pragma: no cover
    _agent_module = None
    input_app = None
    main_app = None
