"""RealtimeAgent factory.

Usage:
    from src.agent import get_agent
    agent = get_agent("default")
"""

from agents.realtime import RealtimeAgent

from prompts import load_prompt
from tools import ALL_TOOLS


def get_agent(prompt: str = "default") -> RealtimeAgent:
    """Build a RealtimeAgent with the given prompt and all registered tools."""
    instructions = load_prompt(prompt)
    return RealtimeAgent(
        name="Assistant",
        instructions=instructions,
        tools=ALL_TOOLS,
    )


