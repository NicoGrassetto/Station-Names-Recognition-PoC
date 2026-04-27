"""Per-connection runtime session.

``Session`` owns everything tied to a single WebSocket client: the socket
itself, the audio buffer, byte counters, the in-progress
:class:`BookingSession` (the domain data being collected), and the
current :class:`State` in the booking finite-state automaton.

Created in :mod:`src.routers.ws` when a client connects, lives in the local
scope of the WebSocket handler, and is garbage-collected on disconnect.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from src.booking import BookingSession
from src.state import LanguageSelectionState, State

logger = logging.getLogger("session")


def _initial_state() -> State:
    return LanguageSelectionState()


@dataclass
class Session:
    client_id: str
    websocket: WebSocket
    booking: BookingSession = field(default_factory=BookingSession)
    audio_buffer: bytearray = field(default_factory=bytearray)
    bytes_received: int = 0
    state: State | None = field(default_factory=_initial_state)

    async def send_json(self, payload: dict[str, Any]) -> None:
        await self.websocket.send_text(json.dumps(payload))

    def transition_to(self, next_state: State | None) -> None:
        """Update the FSA state and log the transition."""
        old = self.state.name if self.state else "None"
        new = next_state.name if next_state else "None"
        logger.info("client %s state %s -> %s", self.client_id, old, new)
        self.state = next_state
