"""Azure AI Voice Live provider scaffold.

The booking state machine, prompts, and tools should stay reusable regardless
of which Voice Live route is implemented first. This file intentionally does
not implement Voice Live networking yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import WebSocket

from src.providers.base import ConversationProviderConfig

VOICE_LIVE_GPT_REALTIME_PHRASE_LIST = "gpt-realtime-phrase-list"
VOICE_LIVE_CUSTOM_SPEECH_AZURE_TTS = "custom-speech-azure-tts"
DEFAULT_VOICE_LIVE_ROUTE = VOICE_LIVE_GPT_REALTIME_PHRASE_LIST


@dataclass(frozen=True)
class VoiceLiveRouteMetadata:
    id: str
    description: str


class VoiceLiveRouteHandler(Protocol):
    metadata: VoiceLiveRouteMetadata

    def active_count(self) -> int: ...

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        config: ConversationProviderConfig,
    ) -> None: ...

    async def disconnect(self, session_id: str) -> None: ...

    async def send_audio(self, session_id: str, audio_bytes: bytes) -> None: ...

    async def commit_audio(self, session_id: str) -> None: ...

    async def interrupt(self, session_id: str) -> None: ...

    async def send_text(self, session_id: str, text: str) -> None: ...


class GPTRealtimePhraseListRoute:
    metadata = VoiceLiveRouteMetadata(
        id=VOICE_LIVE_GPT_REALTIME_PHRASE_LIST,
        description="Voice Live using GPT Realtime with Azure Speech phrase list input customization.",
    )

    def active_count(self) -> int:
        return 0

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        config: ConversationProviderConfig,
    ) -> None:
        # VOICE LIVE: Open a Voice Live WebSocket session using the GPT Realtime route, configure Azure Speech input with src.phrase_list.get_phrase_list(locale), register the booking tools, and wire BookingContext.on_state_change to push updated state prompts.
        raise NotImplementedError(
            "Voice Live route 'gpt-realtime-phrase-list' is not implemented yet."
        )

    async def disconnect(self, session_id: str) -> None:
        # VOICE LIVE: Close the GPT Realtime + phrase-list Voice Live session and remove session-local BookingContext/audio buffers.
        return None

    async def send_audio(self, session_id: str, audio_bytes: bytes) -> None:
        # VOICE LIVE: Forward browser PCM16 chunks to the GPT Realtime route's Voice Live audio input stream.
        raise NotImplementedError(
            "Voice Live GPT Realtime phrase-list audio streaming is not implemented yet."
        )

    async def commit_audio(self, session_id: str) -> None:
        # VOICE LIVE: Commit the active GPT Realtime phrase-list input turn.
        raise NotImplementedError(
            "Voice Live GPT Realtime phrase-list audio commit is not implemented yet."
        )

    async def interrupt(self, session_id: str) -> None:
        # VOICE LIVE: Send the GPT Realtime route's interruption/cancel event and stop queued audio.
        raise NotImplementedError(
            "Voice Live GPT Realtime phrase-list interruption is not implemented yet."
        )

    async def send_text(self, session_id: str, text: str) -> None:
        # VOICE LIVE: Send a text user turn into the GPT Realtime phrase-list route while preserving the booking state/tool loop.
        raise NotImplementedError(
            "Voice Live GPT Realtime phrase-list text input is not implemented yet."
        )


class CustomSpeechAzureTtsRoute:
    metadata = VoiceLiveRouteMetadata(
        id=VOICE_LIVE_CUSTOM_SPEECH_AZURE_TTS,
        description="Voice Live using Azure Speech custom Speech input and Azure TTS output.",
    )

    def active_count(self) -> int:
        return 0

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        config: ConversationProviderConfig,
    ) -> None:
        # VOICE LIVE: Open a Voice Live WebSocket session using Azure Speech input customization with custom Speech model IDs per locale, configure Azure TTS output, register booking tools, and wire BookingContext.on_state_change to push updated state prompts.
        raise NotImplementedError(
            "Voice Live route 'custom-speech-azure-tts' is not implemented yet."
        )

    async def disconnect(self, session_id: str) -> None:
        # VOICE LIVE: Close the custom Speech + Azure TTS Voice Live session and remove session-local BookingContext/audio buffers.
        return None

    async def send_audio(self, session_id: str, audio_bytes: bytes) -> None:
        # VOICE LIVE: Forward browser PCM16 chunks to Voice Live so its Azure Speech custom Speech input handles transcription.
        raise NotImplementedError(
            "Voice Live custom Speech + Azure TTS audio streaming is not implemented yet."
        )

    async def commit_audio(self, session_id: str) -> None:
        # VOICE LIVE: Commit the active Voice Live input turn and let Voice Live drive model/tool handling and Azure TTS output.
        raise NotImplementedError(
            "Voice Live custom Speech + Azure TTS audio commit is not implemented yet."
        )

    async def interrupt(self, session_id: str) -> None:
        # VOICE LIVE: Send the route-specific interruption/cancel event and stop any queued Azure TTS audio.
        raise NotImplementedError(
            "Voice Live custom Speech + Azure TTS interruption is not implemented yet."
        )

    async def send_text(self, session_id: str, text: str) -> None:
        # VOICE LIVE: Send a text user turn into the custom Speech + Azure TTS Voice Live route while preserving the booking state/tool loop.
        raise NotImplementedError(
            "Voice Live custom Speech + Azure TTS text input is not implemented yet."
        )


class VoiceLiveProvider:
    """Provider shell that dispatches to a selected Voice Live route."""

    name = "voice-live"

    def __init__(self) -> None:
        route_handlers: tuple[VoiceLiveRouteHandler, ...] = (
            GPTRealtimePhraseListRoute(),
            CustomSpeechAzureTtsRoute(),
        )
        self._routes = {route.metadata.id: route for route in route_handlers}
        self._session_routes: dict[str, str] = {}

    def active_count(self) -> int:
        return sum(route.active_count() for route in self._routes.values())

    def status_metadata(self) -> dict[str, object]:
        return {
            "status": "not_implemented",
            "disabled": True,
            "reason": "Voice Live provider routes are scaffolded but not implemented yet.",
        }

    def route_metadata(self) -> list[dict[str, object]]:
        return [
            {
                "id": route.metadata.id,
                "description": route.metadata.description,
                "status": "not_implemented",
                "disabled": True,
                "reason": "Route is scaffolded but not implemented yet.",
            }
            for route in self._routes.values()
        ]

    def _resolve_route(self, route: str | None) -> VoiceLiveRouteHandler:
        requested = route or DEFAULT_VOICE_LIVE_ROUTE
        try:
            return self._routes[requested]
        except KeyError as exc:
            raise ValueError(
                f"Unknown Voice Live route '{requested}'. Available: {sorted(self._routes)}"
            ) from exc

    def _route_for_session(self, session_id: str) -> VoiceLiveRouteHandler:
        route_id = self._session_routes.get(session_id)
        if route_id is None:
            raise ValueError(
                f"No Voice Live route is active for session '{session_id}'."
            )
        return self._routes[route_id]

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        config: ConversationProviderConfig,
    ) -> None:
        route = self._resolve_route(config.route)
        self._session_routes[session_id] = route.metadata.id
        try:
            await route.connect(websocket, session_id, config)
        except Exception:
            self._session_routes.pop(session_id, None)
            raise

    async def disconnect(self, session_id: str) -> None:
        route_id = self._session_routes.pop(session_id, None)
        if route_id is None:
            return
        await self._routes[route_id].disconnect(session_id)

    async def send_audio(self, session_id: str, audio_bytes: bytes) -> None:
        await self._route_for_session(session_id).send_audio(session_id, audio_bytes)

    async def commit_audio(self, session_id: str) -> None:
        await self._route_for_session(session_id).commit_audio(session_id)

    async def interrupt(self, session_id: str) -> None:
        await self._route_for_session(session_id).interrupt(session_id)

    async def send_text(self, session_id: str, text: str) -> None:
        await self._route_for_session(session_id).send_text(session_id, text)
