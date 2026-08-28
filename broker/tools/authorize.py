from services.jit_credentials import generate_jit_credentials
from services.policy_engine import is_allowed


def authorize(tool_name: str, agent_id: str) -> dict[str, object]:
    authorized = is_allowed(tool_name)
    return {
        "authorized": authorized,
        "agent_id": agent_id,
        "tool_name": tool_name,
        "jit_credential": generate_jit_credentials() if authorized else None,
    }
