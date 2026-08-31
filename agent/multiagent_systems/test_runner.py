import asyncio
import sys
import os
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from support_agent.agent import app
from google.adk.runners import InMemoryRunner
from google.genai import types

async def run_app():
    pr_url = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/google/google-genai/pull/1"
    print(f"--- Running PR Risk Assessor ADK App ---")
    print(f"Input PR: {pr_url}\n")
    
    runner = InMemoryRunner(app=app)
    
    # Create session
    session = await runner.session_service.create_session(
        app_name="support_agent", user_id="test_user"
    )
    
    # Run the app
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=pr_url)]),
    ):
        # Print output content if present
        if event.content:
            for part in event.content.parts:
                if part.text:
                    print(part.text, end="")
        
        # Print node output values if helpful
        if event.output is not None:
            print(f"\n[Node Output]: {event.output}\n")

def main():
    try:
        asyncio.run(run_app())
    except Exception as e:
        print(f"\nExecution Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
