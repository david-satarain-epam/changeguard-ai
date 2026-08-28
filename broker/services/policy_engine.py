ALLOWED_TOOLS = {"analyze_pr", "run_tests", "get_status"}


def is_allowed(tool_name: str) -> bool:
    return tool_name in ALLOWED_TOOLS
