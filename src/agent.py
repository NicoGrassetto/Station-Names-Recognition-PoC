"""RealtimeAgent factory.

Two flavors:

* :func:`get_agent` — original prompt-driven agent (unchanged behavior).
* :func:`get_booking_agent` — state-aware booking agent. Takes a
  :class:`~src.booking.BookingContext` and exposes the booking tools
  bound to that context, with the initial system prompt taken from the
  context's current state.
"""

from agents.realtime import RealtimeAgent

from prompts import load_prompt
from tools import ALL_TOOLS

from src.booking import BookingContext
from tools.booking import make_booking_tools


def get_agent(prompt: str = "default") -> RealtimeAgent:
    """Build a RealtimeAgent with the given prompt and all registered tools."""
    instructions = load_prompt(prompt)
    return RealtimeAgent(
        name="Assistant",
        instructions=instructions,
        tools=ALL_TOOLS,
    )


def get_booking_agent(ctx: BookingContext) -> RealtimeAgent:
    """Build a state-aware RealtimeAgent for the booking flow."""
    return RealtimeAgent(
        name="BookingAssistant",
        instructions=ctx.state.load_prompt(),
        tools=make_booking_tools(ctx),
    )


