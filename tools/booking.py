"""Booking flow function tools.

These tools mutate a per-session :class:`~src.booking.BookingContext` and
drive the state machine in :mod:`src.state`. Because each tool closes over a
specific ``ctx``, they're built per-session via :func:`make_booking_tools`
rather than exposed as module-level singletons (so the auto-discovery in
``tools/__init__.py`` correctly skips them).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from agents import function_tool
from agents.tool import FunctionTool

from src.state import (
    ConfirmationState,
    DestinationSelectionState,
    DetailsSelectionState,
    EndState,
    LanguageSelectionState,
    ProductSelectionState,
)
from src.booking import BookingContext

logger = logging.getLogger(__name__)


def make_booking_tools(ctx: BookingContext) -> list[FunctionTool]:
    """Build a fresh set of tools bound to ``ctx``.

    The tools mutate ``ctx`` in-place. After every transition they invoke
    ``ctx.on_state_change`` so the manager can push the new state's prompt
    back to the realtime model.
    """

    async def _advance(action: str) -> None:
        if ctx.state is None:
            return
        ctx.state = ctx.state.confirm() if action == "confirm" else ctx.state.cancel()
        if ctx.on_state_change is not None:
            await ctx.on_state_change(ctx)

    @function_tool
    async def set_language(language: str) -> str:
        """Record the user's chosen UI language and advance to product selection.

        Args:
            language: One of \"French\", \"Flemish\", \"English\".
        """
        if not isinstance(ctx.state, LanguageSelectionState):
            return f"Not in language selection (current: {ctx.state_name()})."
        norm = language.strip().capitalize()
        if norm not in {"French", "Flemish", "English"}:
            return f"Unsupported language '{language}'. Use French, Flemish, or English."
        ctx.language = norm
        await _advance("confirm")
        return f"Language set to {norm}. Now in {ctx.state_name()}."

    @function_tool
    async def set_tier(tier: str) -> str:
        """Record the chosen fare tier and advance to destination selection.

        Args:
            tier: One of \"Standard\", \"Comfort\", \"First\".
        """
        if not isinstance(ctx.state, ProductSelectionState):
            return f"Not in product selection (current: {ctx.state_name()})."
        norm = tier.strip().capitalize()
        if norm not in {"Standard", "Comfort", "First"}:
            return f"Unsupported tier '{tier}'. Use Standard, Comfort, or First."
        ctx.tier = norm
        await _advance("confirm")
        return f"Tier set to {norm}. Now in {ctx.state_name()}."

    @function_tool
    async def set_destination(destination: str) -> str:
        """Record the destination station and advance to details selection.

        Args:
            destination: The destination station name as confirmed by the user.
        """
        if not isinstance(ctx.state, DestinationSelectionState):
            return f"Not in destination selection (current: {ctx.state_name()})."
        ctx.destination = destination.strip()
        await _advance("confirm")
        return f"Destination set to '{ctx.destination}'. Now in {ctx.state_name()}."

    @function_tool
    async def lookup_trains(date: str, origin: Optional[str] = None) -> str:
        """Look up available trains from `origin` to the chosen destination on `date`.

        Returns a (mocked) list of train options the assistant can read out so
        the user can pick a departure time before details are finalised.

        Args:
            date: Outbound date in YYYY-MM-DD.
            origin: Origin station. Defaults to "Brussels-Central" if omitted.
        """
        if not isinstance(ctx.state, DetailsSelectionState):
            return f"Not in details selection (current: {ctx.state_name()})."
        if not ctx.destination:
            return "No destination set yet — cannot look up trains."
        org = (origin or "Brussels-Central").strip()
        # Deterministic mock schedule keyed off date so the agent gets stable
        # results across multiple calls within the same booking.
        seed = sum(ord(c) for c in (date + ctx.destination)) % 4
        base_hours = [7, 9, 12, 15, 18]
        durations = [42, 55, 68, 75, 90]
        trains = []
        for i in range(3):
            h = base_hours[(seed + i) % len(base_hours)]
            dur = durations[(seed + i) % len(durations)]
            arr_h = (h * 60 + dur) // 60
            arr_m = (h * 60 + dur) % 60
            trains.append(
                {
                    "train_no": f"IC{1500 + ((seed + i) * 7) % 500}",
                    "depart": f"{h:02d}:00",
                    "arrive": f"{arr_h:02d}:{arr_m:02d}",
                    "duration_min": dur,
                    "fare_eur": 12 + ((seed + i) * 3) % 25,
                }
            )
        logger.info(
            "[mock] lookup_trains origin=%s dest=%s date=%s -> %d options",
            org, ctx.destination, date, len(trains),
        )
        return json.dumps(
            {
                "origin": org,
                "destination": ctx.destination,
                "date": date,
                "trains": trains,
            }
        )

    @function_tool
    async def set_details(
        date: str,
        round_trip: bool,
        passengers: int,
        return_date: Optional[str] = None,
    ) -> str:
        """Record trip details and advance to confirmation.

        Args:
            date: Outbound date in YYYY-MM-DD.
            round_trip: True if the user wants a return ticket.
            passengers: Number of passengers (>= 1).
            return_date: Return date in YYYY-MM-DD (required if round_trip).
        """
        if not isinstance(ctx.state, DetailsSelectionState):
            return f"Not in details selection (current: {ctx.state_name()})."
        if passengers < 1:
            return "Passengers must be at least 1."
        if round_trip and not return_date:
            return "Round-trip requires a return_date."
        ctx.date = date
        ctx.round_trip = bool(round_trip)
        ctx.return_date = return_date if round_trip else None
        ctx.passengers = int(passengers)
        await _advance("confirm")
        return f"Details recorded. Now in {ctx.state_name()}."

    @function_tool
    async def send_purchase_confirmation_to_phone() -> str:
        """Send a (mock) push notification to the user's phone to complete the purchase."""
        if not isinstance(ctx.state, ConfirmationState):
            return f"Not in confirmation step (current: {ctx.state_name()})."
        order_id = "ORD-" + os.urandom(3).hex().upper()
        logger.info(
            "[mock] Sending purchase confirmation to phone for order=%s slots=%s",
            order_id,
            ctx.summary(),
        )
        await _advance("confirm")
        return json.dumps(
            {
                "status": "sent",
                "channel": "phone_push",
                "order_id": order_id,
                "summary": ctx.summary(),
            }
        )

    @function_tool
    async def send_receipt(method: str) -> str:
        """Send a (mock) receipt to the user via the chosen channel.

        Args:
            method: \"email\" or \"sms\".
        """
        if not isinstance(ctx.state, EndState):
            return f"Not in end step (current: {ctx.state_name()})."
        m = method.strip().lower()
        if m not in {"email", "sms"}:
            return "method must be 'email' or 'sms'."
        logger.info("[mock] Sending %s receipt for slots=%s", m, ctx.summary())
        return json.dumps({"status": "sent", "method": m, "summary": ctx.summary()})

    @function_tool
    async def cancel_step() -> str:
        """Go back to the previous step in the booking flow."""
        await _advance("cancel")
        return f"Went back. Now in {ctx.state_name()}."

    return [
        set_language,
        set_tier,
        set_destination,
        lookup_trains,
        set_details,
        send_purchase_confirmation_to_phone,
        send_receipt,
        cancel_step,
    ]
