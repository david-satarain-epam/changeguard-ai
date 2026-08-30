"""
Policy Engine.
Loads policies from YAML. Checks if an agent is allowed to call a tool.
"""

import yaml
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("changeguard-broker.policy")


class PolicyEngine:
    """Checks authorization policies for agent tool calls."""

    def __init__(self, policy_path: str = None):
        if policy_path is None:
            base_path = Path(__file__).parent.parent
            policy_path = base_path / "data" / "policies.yaml"
        with open(policy_path) as f:
            config = yaml.safe_load(f)

        self.policies: dict[str, dict] = {}
        for p in config.get("policies", []):
            self.policies[p["agent_id"]] = p

        logger.info("Loaded %d policies", len(self.policies))

    def get_policy(self, agent_id: str) -> Optional[dict]:
        """Get the policy for an agent."""
        return self.policies.get(agent_id)

    def is_allowed(self, agent_id: str, tool_name: str) -> tuple[bool, str]:
        """
        Check if an agent is allowed to call a tool.

        Returns:
            (allowed: bool, reason: str)
        """
        policy = self.get_policy(agent_id)

        # Unknown agent
        if policy is None:
            logger.warning("Unknown agent blocked: %s", agent_id)
            return False, f"Agent '{agent_id}' is not registered."

        # Explicit block
        if policy.get("action") == "BLOCK":
            logger.warning("Blocked agent: %s", agent_id)
            return False, f"Agent '{agent_id}' is explicitly blocked."

        # Check tool list
        allowed_tools = policy.get("allowed_tools", [])
        if tool_name not in allowed_tools:
            logger.warning(
                "Tool '%s' not allowed for agent '%s'", tool_name, agent_id
            )
            return False, (
                f"Tool '{tool_name}' is not allowed for agent '{agent_id}'. "
                f"Allowed: {allowed_tools}"
            )

        logger.info("Agent '%s' authorized for tool '%s'", agent_id, tool_name)
        return True, "Authorized"

    def requires_approval(self, agent_id: str, tool_name: str) -> bool:
        """Check if this tool requires explicit approval."""
        policy = self.get_policy(agent_id)
        if policy is None:
            return False
        return tool_name in policy.get("require_approval_for", [])