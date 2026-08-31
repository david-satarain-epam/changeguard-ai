import asyncio
import sys
import os
import json
import dotenv

dotenv.load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent import input_app, main_app
from google.adk.runners import InMemoryRunner
from google.genai import types


# ─── Phase 1: Conversational URL input ──────────────────────────

async def get_repo_url_from_agent() -> str:
    """Run the input_agent to prompt for and validate the repository URL."""
    runner  = InMemoryRunner(app=input_app)
    session = await runner.session_service.create_session(
        app_name="input_agent", user_id="test_user"
    )

    # Send an initial message to trigger the agent's prompt
    prompt = ""
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(
            role="user", parts=[types.Part.from_text(text="hello")]
        ),
    ):
        if event.content:
            for part in event.content.parts:
                if part.text:
                    prompt += part.text

    print(prompt.strip())
    repo_url = input("> ").strip()

    # Pass the URL back to the agent for validation/extraction
    validated = repo_url
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(
            role="user", parts=[types.Part.from_text(text=repo_url)]
        ),
    ):
        if event.content:
            for part in event.content.parts:
                if part.text:
                    text = part.text.strip()
                    if "github.com" in text:
                        validated = text

    return validated


# ─── Phase 2: Main analysis workflow ────────────────────────────

async def run_analysis(repo_url: str):
    """Run the PR risk assessment workflow against the given repository."""
    print(f"\n--- Analyzing repository: {repo_url} ---\n")

    runner  = InMemoryRunner(app=main_app)
    session = await runner.session_service.create_session(
        app_name="support_agent", user_id="test_user"
    )

    final_output = ""

    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(
            role="user", parts=[types.Part.from_text(text=repo_url)]
        ),
    ):
        if event.content:
            for part in event.content.parts:
                if part.text:
                    final_output += part.text

        if event.output is not None:
            label   = getattr(event, "node_name", "Node")
            summary = json.dumps(event.output) if isinstance(event.output, dict) else str(event.output)
            if len(summary) > 200:
                summary = summary[:200] + "..."
            print(f"[{label}]: {summary}\n")

    # Pretty-print the final JSON report
    print("\n--- PR Risk Assessment Report ---\n")
    output = final_output.strip()
    if output:
        # Strip markdown code fences if the model added them
        if output.startswith("```"):
            output = re.sub(r"^```[a-z]*\n?", "", output)
            output = re.sub(r"\n?```$", "", output)
        try:
            parsed = json.loads(output)
            print(json.dumps(parsed, indent=2))
        except json.JSONDecodeError:
            print(output)
    else:
        print("(no output received)")


# ─── Entry point ─────────────────────────────────────────────────

async def main():
    print("--- ChangeGuard AI: PR Risk Assessor ---")

    repo_url = sys.argv[1] if len(sys.argv) > 1 else None

    if repo_url:
        # URL passed as CLI argument — skip the conversational step
        await run_analysis(repo_url)
    else:
        # Conversational mode — input_agent asks for the URL
        repo_url = await get_repo_url_from_agent()
        await run_analysis(repo_url)


if __name__ == "__main__":
    import re
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as exc:
        print(f"\nExecution failed: {exc}")
        import traceback
        traceback.print_exc()
