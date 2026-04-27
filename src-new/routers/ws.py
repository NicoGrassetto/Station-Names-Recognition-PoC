"""WebSocket endpoint that talks to the browser front-end.

A new :class:`Session` is created per connection (see :mod:`src.session`)
and lives in the local scope of :func:`websocket_endpoint`. It owns the
WebSocket, the audio buffer, byte counters, and the in-progress
:class:`BookingSession`. When the client disconnects, the session goes
out of scope and is garbage-collected — no global registry needed.

Wire contract
-------------
- Path: ``/ws/{client_id}``
- **Binary** frames carry raw audio: PCM 16-bit little-endian, mono, 16 kHz
  (~100 ms / 3200 bytes per chunk recommended).
- **Text** frames carry JSON control / event messages.

Client → server JSON messages::

    { "type": "start", "lang": "fr-FR", "sample_rate": 16000 }
    { "type": "stop" }
    { "type": "confirm" }   # advance the booking FSA
    { "type": "cancel" }    # go back one step in the booking FSA

Server → client JSON messages::

    { "type": "ready",         "client_id": "..." }
    { "type": "started",       "lang": "fr-FR", "sample_rate": 16000 }
    { "type": "ack",           "bytes": 3200, "total_bytes": 32000 }
    { "type": "stopped",       "total_bytes": 32000 }
    { "type": "transcription", "text": "Brussels Central", "locale": "fr-FR" }
    { "type": "booking_state", "state": "DestinationSelectionState",
                               "prompt": "..." }
    { "type": "error",         "message": "..." }
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.session import Session
from src.speech import transcribe_destination_audio
from src.state import DestinationSelectionState

logger = logging.getLogger("ws-audio")

# Locale used for Azure Custom Speech when the booking language hasn't been
# pinned yet (e.g. user starts speaking before LanguageSelectionState confirms).
_DEFAULT_LOCALE = "fr-FR"

_LANGUAGE_TO_LOCALE = {
    "French": "fr-FR",
    "Flemish": "fr-FR",  # no Flemish custom endpoint trained yet
    "English": "en-US",
    "Dutch": "fr-FR",
    "German": "fr-FR",
}

router = APIRouter()


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------


async def _handle_text_message(session: Session, raw: str) -> None:
    """Parse and dispatch a JSON control message from the client."""
    try:
        message: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("client %s sent invalid JSON: %r", session.client_id, raw[:200])
        await session.send_json({"type": "error", "message": "invalid_json"})
        return

    message_type = message.get("type")
    logger.debug("client %s text msg %s", session.client_id, message)

    if message_type == "start":
        lang = message.get("lang", "fr-FR")
        sample_rate = int(message.get("sample_rate", 16000))
        session.bytes_received = 0
        session.audio_buffer.clear()
        logger.info(
            "client %s START lang=%s rate=%d", session.client_id, lang, sample_rate
        )
        await session.send_json(
            {"type": "started", "lang": lang, "sample_rate": sample_rate}
        )

    elif message_type == "stop":
        logger.info(
            "client %s STOP state=%s total_bytes=%d booking=%s",
            session.client_id,
            session.state.name if session.state else "None",
            session.bytes_received,
            session.booking.snapshot(),
        )
        # Destination capture uses Azure Custom Speech (NOT Whisper) so the
        # NMBS-fine-tuned model can recognize Belgian/French station names.
        if isinstance(session.state, DestinationSelectionState):
            await _transcribe_destination(session)
        await session.send_json(
            {"type": "stopped", "total_bytes": session.bytes_received}
        )

    elif message_type == "confirm":
        if session.state is None:
            await session.send_json({"type": "error", "message": "no_state"})
            return
        next_state = session.state.confirm()
        session.transition_to(next_state)
        await _announce_state(session)

    elif message_type == "cancel":
        if session.state is None:
            await session.send_json({"type": "error", "message": "no_state"})
            return
        next_state = session.state.cancel()
        session.transition_to(next_state)
        await _announce_state(session)

    else:
        # The frontend may still be on the old wire contract; warn but don't
        # spam the client with errors per chunk.
        logger.warning(
            "client %s ignoring unknown msg type %r", session.client_id, message_type
        )


async def _handle_audio_chunk(session: Session, chunk: bytes) -> None:
    """Acknowledge a binary audio chunk. Forwarding is added in the next layer."""
    session.audio_buffer.extend(chunk)
    session.bytes_received += len(chunk)
    # Log every ~1 s of audio (assuming 16 kHz mono 16-bit = 32000 B/s) so we
    # don't spam at 10 Hz, but still see progress.
    if session.bytes_received // 32000 != (session.bytes_received - len(chunk)) // 32000:
        logger.info(
            "client %s audio %d B (~%.1f s buffered)",
            session.client_id,
            session.bytes_received,
            session.bytes_received / 32000,
        )
    else:
        logger.debug(
            "client %s chunk %d B total %d B",
            session.client_id,
            len(chunk),
            session.bytes_received,
        )
    await session.send_json(
        {
            "type": "ack",
            "bytes": len(chunk),
            "total_bytes": session.bytes_received,
        }
    )


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


async def _announce_state(session: Session) -> None:
    """Tell the client which FSA state we just entered (and the system prompt)."""
    if session.state is None:
        await session.send_json({"type": "booking_state", "state": None})
        return
    await session.send_json(
        {
            "type": "booking_state",
            "state": session.state.name,
            "prompt": session.state.load_prompt(),
        }
    )


def _resolve_locale(session: Session) -> str:
    lang = session.booking.language
    if lang and lang in _LANGUAGE_TO_LOCALE:
        return _LANGUAGE_TO_LOCALE[lang]
    return _DEFAULT_LOCALE


async def _transcribe_destination(session: Session) -> None:
    """Run the buffered audio through Azure Custom Speech and update booking."""
    locale = _resolve_locale(session)
    pcm = bytes(session.audio_buffer)
    try:
        text = transcribe_destination_audio(pcm, locale)
    except Exception:
        logger.exception("client %s Azure Speech failed", session.client_id)
        await session.send_json({"type": "error", "message": "speech_failed"})
        return
    if text:
        session.booking.arrival_station = text
    await session.send_json(
        {"type": "transcription", "text": text, "locale": locale}
    )


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str) -> None:
    await websocket.accept()
    session = Session(client_id=client_id, websocket=websocket)
    logger.info(
        "client %s connected, initial state=%s",
        client_id,
        session.state.name if session.state else "None",
    )
    await session.send_json({"type": "ready", "client_id": client_id})
    await _announce_state(session)

    try:
        while True:
            # ``receive`` returns either {"text": "..."} or {"bytes": b"..."}.
            message = await websocket.receive()

            # Starlette delivers the disconnect as a regular message; surface
            # it explicitly so the loop exits cleanly.
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(code=message.get("code", 1000))

            if "text" in message and message["text"] is not None:
                await _handle_text_message(session, message["text"])
            elif "bytes" in message and message["bytes"] is not None:
                await _handle_audio_chunk(session, message["bytes"])

    except WebSocketDisconnect as exc:
        logger.info("client %s disconnected (code=%s)", client_id, exc.code)
    except Exception:
        logger.exception("websocket error for client %s", client_id)
