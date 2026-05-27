"""Azure OpenAI GPT Realtime provider.

This module preserves the current Realtime implementation behind the provider
interface so alternate providers can be introduced without changing the booking
state machine, prompts, tools, or browser wire contract.

ORIGINAL: Custom Speech used as patch in the orchestration of GPT-Realtime.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import WebSocket
from typing_extensions import assert_never

from azure.identity import DefaultAzureCredential

from agents.realtime import RealtimeRunner, RealtimeSession, RealtimeSessionEvent
from agents.realtime.config import RealtimeUserInputMessage
from agents.realtime.items import RealtimeItem
from agents.realtime.model import RealtimeModelConfig
from agents.realtime.model_inputs import RealtimeModelSendRawMessage

from config import load_session_config
from src.agent import get_booking_agent
from src.booking import (
    BookingContext,
    DestinationSelectionState,
    get_speech_endpoint_id,
    transcribe_destination_audio,
)
from src.providers.base import ConversationProviderConfig

logger = logging.getLogger("gpt-realtime-provider")

load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-realtime-1-5")

_credential = DefaultAzureCredential()


def _get_azure_token() -> str:
    token = _credential.get_token("https://cognitiveservices.azure.com/.default")
    return token.token


def _build_realtime_url(deployment: str | None = None) -> str:
    if not AZURE_OPENAI_ENDPOINT:
        raise ValueError("AZURE_OPENAI_ENDPOINT is not configured")
    dep = deployment or AZURE_OPENAI_DEPLOYMENT
    host = AZURE_OPENAI_ENDPOINT.rstrip("/")
    host = host.replace("https://", "wss://").replace("http://", "ws://")
    if not host.startswith("ws"):
        host = f"wss://{host}"
    return f"{host}/openai/v1/realtime?model={dep}"


def _build_model_settings(mode: str, deployment: str | None = None) -> dict[str, Any]:
    """Translate YAML config into SDK RealtimeSessionModelSettings."""
    cfg = load_session_config(mode)

    model_name = deployment or AZURE_OPENAI_DEPLOYMENT
    settings: dict[str, Any] = {"model_name": model_name}

    modalities = cfg.get("modalities", ["text", "audio"])
    if "audio" in modalities:
        settings["output_modalities"] = ["audio"]
    else:
        settings["output_modalities"] = ["text"]

    audio_input: dict[str, Any] = {}
    audio_output: dict[str, Any] = {}

    audio_input["format"] = cfg.get("input_audio_format", "pcm16")

    td = cfg.get("turn_detection")
    if td is None:
        audio_input["turn_detection"] = None
    elif isinstance(td, dict):
        td_type = td.get("type", "server_vad")
        if td_type == "semantic_vad":
            clean_td: dict[str, Any] = {"type": "semantic_vad"}
            if "eagerness" in td:
                clean_td["eagerness"] = td["eagerness"]
        else:
            clean_td = {
                k: v
                for k, v in td.items()
                if k
                in (
                    "type",
                    "threshold",
                    "prefix_padding_ms",
                    "silence_duration_ms",
                    "create_response",
                    "interrupt_response",
                )
            }
        audio_input["turn_detection"] = clean_td

    transcription = cfg.get("input_audio_transcription")
    if transcription:
        audio_input["transcription"] = transcription

    audio_output["format"] = cfg.get("output_audio_format", "pcm16")

    voice = cfg.get("voice")
    if voice:
        audio_output["voice"] = voice

    settings["audio"] = {}
    if audio_input:
        settings["audio"]["input"] = audio_input
    if audio_output:
        settings["audio"]["output"] = audio_output

    return settings


class GPTRealtimeProvider:
    """Manages Azure OpenAI GPT Realtime sessions for browser clients."""

    name = "gpt-realtime"

    def __init__(self) -> None:
        self.active_sessions: dict[str, RealtimeSession] = {}
        self.session_contexts: dict[str, Any] = {}
        self.websockets: dict[str, WebSocket] = {}
        self.event_tasks: dict[str, asyncio.Task[None]] = {}
        self.booking_contexts: dict[str, BookingContext] = {}
        self.destination_audio_buffers: dict[str, bytearray] = {}
        self.destination_transcribing: set[str] = set()
        self.collect_mode_state: dict[str, str] = {}
        self.session_tools: dict[str, list[Any]] = {}
        self.audio_bytes_received: dict[str, int] = {}

    def active_count(self) -> int:
        return len(self.active_sessions)

    def status_metadata(self) -> dict[str, object]:
        if not AZURE_OPENAI_ENDPOINT:
            return {
                "status": "unavailable",
                "disabled": True,
                "reason": "AZURE_OPENAI_ENDPOINT is not configured.",
            }
        return {
            "status": "available",
            "disabled": False,
            "reason": None,
        }

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        config: ConversationProviderConfig,
    ) -> None:
        await websocket.accept()
        self.websockets[session_id] = websocket

        booking_ctx = BookingContext()
        self.booking_contexts[session_id] = booking_ctx
        self.destination_audio_buffers[session_id] = bytearray()
        self.audio_bytes_received[session_id] = 0
        agent = get_booking_agent(booking_ctx)
        self.session_tools[session_id] = list(agent.tools)

        runner = RealtimeRunner(agent)

        token = _get_azure_token()
        model_config: RealtimeModelConfig = {
            "url": _build_realtime_url(config.model),
            "headers": {"authorization": f"Bearer {token}"},
            "initial_model_settings": _build_model_settings(config.mode, config.model),
        }

        session_context = await runner.run(model_config=model_config)
        session = await session_context.__aenter__()
        self.active_sessions[session_id] = session
        self.session_contexts[session_id] = session_context

        async def _on_state_change(ctx: BookingContext) -> None:
            await self._on_booking_state_change(session_id, ctx)

        booking_ctx.on_state_change = _on_state_change

        self.event_tasks[session_id] = asyncio.create_task(
            self._process_events(session_id)
        )

        deployment = config.model or AZURE_OPENAI_DEPLOYMENT
        await self._send_log(
            session_id,
            "session",
            f"Connected (mode={config.mode})",
            realtime_model=deployment,
            mode=config.mode,
            provider=self.name,
        )
        if booking_ctx.state is not None:
            await self._send_log(
                session_id,
                "state",
                f"Initial state: {type(booking_ctx.state).__name__}",
                state=type(booking_ctx.state).__name__,
            )
        await self._send_log(
            session_id,
            "session",
            "Starting initial assistant response",
            state=booking_ctx.state_name(),
        )
        await self._send_client_event(session_id, {"type": "response.create"})

    async def disconnect(self, session_id: str) -> None:
        task = self.event_tasks.pop(session_id, None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if session_id in self.session_contexts:
            await self.session_contexts[session_id].__aexit__(None, None, None)
            del self.session_contexts[session_id]
        self.active_sessions.pop(session_id, None)
        self.websockets.pop(session_id, None)
        self.booking_contexts.pop(session_id, None)
        self.destination_audio_buffers.pop(session_id, None)
        self.destination_transcribing.discard(session_id)
        self.collect_mode_state.pop(session_id, None)
        self.session_tools.pop(session_id, None)
        self.audio_bytes_received.pop(session_id, None)

    async def send_audio(self, session_id: str, audio_bytes: bytes) -> None:
        previous_total = self.audio_bytes_received.get(session_id, 0)
        new_total = previous_total + len(audio_bytes)
        self.audio_bytes_received[session_id] = new_total
        # Log roughly once per second of 24 kHz mono PCM16 input.
        if previous_total // 48_000 != new_total // 48_000:
            await self._send_log(
                session_id,
                "audio",
                "Receiving microphone audio",
                bytes_received=new_total,
            )
        ctx = self.booking_contexts.get(session_id)
        if ctx is not None and isinstance(ctx.state, DestinationSelectionState):
            self.destination_audio_buffers[session_id].extend(audio_bytes)
        if session_id in self.active_sessions:
            await self.active_sessions[session_id].send_audio(audio_bytes)

    async def commit_audio(self, session_id: str) -> None:
        ctx = self.booking_contexts.get(session_id)
        if ctx is not None and isinstance(ctx.state, DestinationSelectionState):
            await self._commit_destination_audio(session_id)
            return
        await self._send_client_event(session_id, {"type": "input_audio_buffer.commit"})

    async def interrupt(self, session_id: str) -> None:
        session = self.active_sessions.get(session_id)
        if not session:
            return
        await session.interrupt()

    async def send_text(self, session_id: str, text: str) -> None:
        if not text:
            return
        await self._set_collect_phase(session_id)
        user_msg: RealtimeUserInputMessage = {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        }
        await self._send_user_message(session_id, user_msg)

    async def _send_client_event(self, session_id: str, event: dict[str, Any]) -> None:
        session = self.active_sessions.get(session_id)
        if not session:
            return
        other_data = {k: v for k, v in event.items() if k != "type"}
        await session.model.send_event(
            RealtimeModelSendRawMessage(
                message={
                    "type": event["type"],
                    "other_data": other_data,
                }
            )
        )

    async def _send_session_update(
        self, session_id: str, session_settings: dict[str, Any]
    ) -> None:
        session = self.active_sessions.get(session_id)
        if not session:
            return
        await self._send_client_event(
            session_id,
            {"type": "session.update", "session": session_settings},
        )

    async def _send_user_message(
        self, session_id: str, message: RealtimeUserInputMessage
    ) -> None:
        session = self.active_sessions.get(session_id)
        if not session:
            return
        await session.send_message(message)

    async def _send_log(
        self,
        session_id: str,
        source: str,
        message: str,
        level: str = "info",
        **meta: Any,
    ) -> None:
        websocket = self.websockets.get(session_id)
        logger.log(
            logging.WARNING if level == "warn" else logging.INFO,
            "[%s] %s | %s",
            source,
            message,
            meta or "",
        )
        if websocket is None:
            return
        payload: dict[str, Any] = {
            "type": "log",
            "level": level,
            "source": source,
            "message": message,
        }
        if meta:
            payload["meta"] = meta
        try:
            await websocket.send_text(json.dumps(payload, default=str))
        except Exception:
            pass

    async def _on_booking_state_change(
        self, session_id: str, ctx: BookingContext
    ) -> None:
        """Push the new state's system prompt to the realtime model and client."""
        websocket = self.websockets.get(session_id)
        if ctx.state is None:
            if websocket is not None:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "booking_state",
                            "state": None,
                            "summary": ctx.summary(),
                        }
                    )
                )
            return

        new_prompt = ctx.state.load_prompt()
        update_payload: dict[str, Any] = {"instructions": new_prompt}
        vad_base = {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 250,
            "interrupt_response": True,
        }
        if isinstance(ctx.state, DestinationSelectionState):
            update_payload["turn_detection"] = {**vad_base, "create_response": False}
        else:
            update_payload["turn_detection"] = {**vad_base, "create_response": True}

        update_payload["tool_choice"] = "none"
        await self._send_session_update(
            session_id,
            update_payload,
        )
        self.destination_audio_buffers[session_id] = bytearray()
        self.collect_mode_state.pop(session_id, None)

        await self._send_log(
            session_id,
            "state",
            f"Transitioned to {type(ctx.state).__name__}",
            state=type(ctx.state).__name__,
            summary=ctx.summary(),
        )
        if websocket is not None:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "booking_state",
                        "state": type(ctx.state).__name__,
                        "summary": ctx.summary(),
                    }
                )
            )

    async def _commit_destination_audio(self, session_id: str) -> None:
        """Transcribe buffered destination audio and inject it as a user message."""
        ctx = self.booking_contexts.get(session_id)
        if ctx is None or not isinstance(ctx.state, DestinationSelectionState):
            return
        if session_id in self.destination_transcribing:
            return
        buf = bytes(self.destination_audio_buffers.get(session_id, b""))
        self.destination_audio_buffers[session_id] = bytearray()
        if not buf:
            return
        self.destination_transcribing.add(session_id)
        locale = ctx.locale()
        endpoint_id = get_speech_endpoint_id(locale)
        await self._send_log(
            session_id,
            "speech",
            f"Transcribing {len(buf)} bytes via Azure Speech ({locale})",
            locale=locale,
            endpoint_id=endpoint_id or "base-model",
            bytes=len(buf),
        )
        try:
            loop = asyncio.get_running_loop()
            try:
                transcript = await loop.run_in_executor(
                    None, transcribe_destination_audio, buf, locale
                )
            except Exception:
                logger.exception("Azure Speech transcription failed")
                await self._send_log(
                    session_id,
                    "speech",
                    "Azure Speech transcription failed",
                    level="warn",
                    locale=locale,
                )
                transcript = ""
        finally:
            self.destination_transcribing.discard(session_id)

        if not transcript:
            await self._send_log(
                session_id,
                "speech",
                "No transcription returned",
                level="warn",
                locale=locale,
            )
            return

        await self._send_log(
            session_id,
            "speech",
            f"Transcribed: {transcript!r}",
            locale=locale,
            endpoint_id=endpoint_id or "base-model",
            transcript=transcript,
        )

        await self._send_user_message(
            session_id,
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"[Azure Speech transcription]: {transcript}",
                    }
                ],
            },
        )
        await self._send_client_event(session_id, {"type": "response.create"})

        websocket = self.websockets.get(session_id)
        if websocket is not None:
            await websocket.send_text(
                json.dumps({"type": "speech_transcript", "text": transcript})
            )

    def _sanitize_history_item(self, item: RealtimeItem) -> dict[str, Any]:
        item_dict = item.model_dump()
        content = item_dict.get("content")
        if isinstance(content, list):
            sanitized: list[Any] = []
            for part in content:
                if isinstance(part, dict):
                    p = part.copy()
                    if p.get("type") in ("audio", "input_audio"):
                        p.pop("audio", None)
                    sanitized.append(p)
                else:
                    sanitized.append(part)
            item_dict["content"] = sanitized
        return item_dict

    async def _serialize_event(self, event: RealtimeSessionEvent) -> dict[str, Any]:
        base: dict[str, Any] = {"type": event.type}

        if event.type == "agent_start":
            base["agent"] = event.agent.name
        elif event.type == "agent_end":
            base["agent"] = event.agent.name
        elif event.type == "handoff":
            base["from"] = event.from_agent.name
            base["to"] = event.to_agent.name
        elif event.type == "tool_start":
            base["tool"] = event.tool.name
        elif event.type == "tool_end":
            base["tool"] = event.tool.name
            base["output"] = str(event.output)
        elif event.type == "tool_approval_required":
            base["tool"] = event.tool.name
            base["call_id"] = event.call_id
            base["arguments"] = event.arguments
            base["agent"] = event.agent.name
        elif event.type == "audio":
            base["audio"] = base64.b64encode(event.audio.data).decode("utf-8")
        elif event.type in ("audio_interrupted", "audio_end"):
            pass
        elif event.type == "history_updated":
            base["history"] = [
                self._sanitize_history_item(item) for item in event.history
            ]
        elif event.type == "history_added":
            try:
                base["item"] = self._sanitize_history_item(event.item)
            except Exception:
                base["item"] = None
        elif event.type == "guardrail_tripped":
            base["guardrail_results"] = [
                {"name": r.guardrail.name} for r in event.guardrail_results
            ]
        elif event.type == "raw_model_event":
            base["raw_model_event"] = {"type": event.data.type}
        elif event.type == "error":
            base["error"] = str(event.error) if hasattr(event, "error") else "Unknown"
        elif event.type == "input_audio_timeout_triggered":
            pass
        else:
            assert_never(event)

        return base

    async def _process_events(self, session_id: str) -> None:
        try:
            session = self.active_sessions[session_id]
            websocket = self.websockets[session_id]

            async for event in session:
                if event.type == "raw_model_event":
                    raw_type = getattr(event.data, "type", None)
                    if raw_type in (
                        "input_audio_buffer.speech_stopped",
                        "input_audio_buffer.committed",
                    ):
                        ctx = self.booking_contexts.get(session_id)
                        if ctx is not None and isinstance(
                            ctx.state, DestinationSelectionState
                        ):
                            asyncio.create_task(
                                self._commit_destination_audio(session_id)
                            )
                    elif raw_type in ("response.done", "turn_ended"):
                        await self._set_collect_phase(session_id)
                if event.type == "tool_start":
                    ctx = self.booking_contexts.get(session_id)
                    await self._send_log(
                        session_id,
                        "tool",
                        f"Calling {event.tool.name}()",
                        tool=event.tool.name,
                        state=ctx.state_name() if ctx else None,
                    )
                elif event.type == "tool_end":
                    await self._send_log(
                        session_id,
                        "tool",
                        f"{event.tool.name}() returned",
                        tool=event.tool.name,
                        output=str(event.output)[:500],
                    )

                event_data = await self._serialize_event(event)
                await websocket.send_text(json.dumps(event_data))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Error processing events for %s: %s", session_id, e)

    async def _set_collect_phase(self, session_id: str) -> None:
        ctx = self.booking_contexts.get(session_id)
        if ctx is None or ctx.state is None:
            self.collect_mode_state.pop(session_id, None)
            return
        state_name = ctx.state_name()
        if self.collect_mode_state.get(session_id) == state_name:
            return

        tool_choice = "auto"
        await self._send_session_update(
            session_id,
            {"tool_choice": tool_choice},
        )
        self.collect_mode_state[session_id] = state_name
        await self._send_log(
            session_id,
            "state",
            "Waiting for user input",
            state=state_name,
            tool_choice=tool_choice,
        )
