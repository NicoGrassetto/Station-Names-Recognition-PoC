"""RealtimeAgent factory for the booking flow."""

from agents.realtime import RealtimeAgent

from src.booking import BookingContext
from tools.booking import make_booking_tools


def get_booking_agent(ctx: BookingContext) -> RealtimeAgent:
    """Build a state-aware RealtimeAgent for the booking flow."""
    return RealtimeAgent(
        name="BookingAssistant",
        instructions=ctx.state.load_prompt(),
        tools=make_booking_tools(ctx),
    )
