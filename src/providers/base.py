"""Provider interface for realtime conversation backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import WebSocket


@dataclass(frozen=True)
class ConversationProviderConfig:
    """Provider-agnostic connection options from the browser WebSocket."""

    mode: str = "booking"
    model: str | None = None
    route: str | None = None


class ConversationProvider(Protocol):
    """Common surface used by the FastAPI WebSocket route."""

    name: str

    def active_count(self) -> int:
        """Return active backend sessions owned by this provider."""
        ...

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        config: ConversationProviderConfig,
    ) -> None:
        """Accept the browser WebSocket and open the provider session."""
        ...

    async def disconnect(self, session_id: str) -> None:
        """Close and clean up provider resources for the session."""
        ...

    async def send_audio(self, session_id: str, audio_bytes: bytes) -> None:
        """Forward a PCM16 audio chunk to the provider."""
        ...

    async def commit_audio(self, session_id: str) -> None:
        """Commit the current input audio turn."""
        ...

    async def interrupt(self, session_id: str) -> None:
        """Interrupt the current provider response."""
        ...

    async def send_text(self, session_id: str, text: str) -> None:
        """Send a text user message to the provider."""
        ...
