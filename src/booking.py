"""Per-session booking context, state-aware tools, and Azure Speech bridge.

The booking flow lives in :mod:`src.state` (the State subclasses). This module
glues that pure state machine to a concrete realtime session:

* :class:`BookingContext` holds the active state, the slot values collected
  so far, and a back-reference to the realtime session so tools can push a
  ``session.update`` whenever the state changes.
* :func:`make_booking_tools` returns a list of ``FunctionTool`` instances
  bound to a specific :class:`BookingContext`.
* :func:`transcribe_destination_audio` pipes a buffered chunk of PCM16 audio
  through the locale-specific custom Azure Speech endpoint and returns the
  recognized text.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import azure.cognitiveservices.speech as speechsdk
from agents import function_tool
from agents.tool import FunctionTool
from azure.identity import DefaultAzureCredential

from src.state import (
    ConfirmationState,
    DestinationSelectionState,
    DetailsSelectionState,
    EndState,
    LanguageSelectionState,
    ProductSelectionState,
    State,
)

logger = logging.getLogger(__name__)

_LANGUAGE_TO_LOCALE = {
    "french": "fr-FR",
    "flemish": "fr-FR",  # no Flemish custom endpoint trained yet — fallback
    "english": "en-US",
}

_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _ROOT / "config" / "custom_speech_endpoints.json"


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@dataclass
class BookingContext:
    """Per-session holder for state + collected slots + session back-ref."""

    state: Optional[State] = field(default_factory=LanguageSelectionState)
    language: Optional[str] = None
    tier: Optional[str] = None
    destination: Optional[str] = None
    date: Optional[str] = None
    round_trip: Optional[bool] = None
    return_date: Optional[str] = None
    passengers: Optional[int] = None

    # Back-reference set by the manager after the session is created so
    # tools can push session.update events when the state changes.
    on_state_change: Any = None  # async callable: (BookingContext) -> None

    def state_name(self) -> str:
        return type(self.state).__name__ if self.state else "None"

    def locale(self) -> str:
        """IANA-style locale derived from the chosen language."""
        if not self.language:
            return "en-US"
        return _LANGUAGE_TO_LOCALE.get(self.language.lower(), "en-US")

    def summary(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "tier": self.tier,
            "destination": self.destination,
            "date": self.date,
            "round_trip": self.round_trip,
            "return_date": self.return_date,
            "passengers": self.passengers,
        }


# ---------------------------------------------------------------------------
# Azure Speech bridge (used while in DestinationSelectionState)
# ---------------------------------------------------------------------------


_credential = DefaultAzureCredential()


def get_speech_endpoint_id(locale: str) -> Optional[str]:
    """Return the custom Speech endpoint id configured for ``locale``, if any."""
    if not _MANIFEST_PATH.exists():
        return None
    try:
        manifest = json.loads(_MANIFEST_PATH.read_text())
    except json.JSONDecodeError:
        return None
    entry = manifest.get(locale)
    if isinstance(entry, dict):
        return entry.get("endpoint_id")
    return None


def _make_speech_config(locale: str) -> speechsdk.SpeechConfig:
    region = os.environ["AZURE_SPEECH_REGION"]
    sub_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    rg = os.environ["AZURE_RESOURCE_GROUP"]
    name = os.environ["AZURE_SPEECH_RESOURCE_NAME"]
    resource_id = (
        f"/subscriptions/{sub_id}/resourceGroups/{rg}"
        f"/providers/Microsoft.CognitiveServices/accounts/{name}"
    )
    token = _credential.get_token(
        "https://cognitiveservices.azure.com/.default"
    ).token
    cfg = speechsdk.SpeechConfig(
        auth_token=f"aad#{resource_id}#{token}", region=region
    )
    cfg.speech_recognition_language = locale

    if _MANIFEST_PATH.exists():
        manifest = json.loads(_MANIFEST_PATH.read_text())
        if locale in manifest:
            cfg.endpoint_id = manifest[locale]["endpoint_id"]

    return cfg


def transcribe_destination_audio(pcm16_24k: bytes, locale: str) -> str:
    """Transcribe a raw PCM16 24 kHz mono buffer via the custom endpoint."""
    if not pcm16_24k:
        return ""

    cfg = _make_speech_config(locale)
    fmt = speechsdk.audio.AudioStreamFormat(
        samples_per_second=24000, bits_per_sample=16, channels=1
    )
    push = speechsdk.audio.PushAudioInputStream(stream_format=fmt)
    audio_in = speechsdk.audio.AudioConfig(stream=push)

    rec = speechsdk.SpeechRecognizer(speech_config=cfg, audio_config=audio_in)
    push.write(pcm16_24k)
    push.close()

    result = rec.recognize_once()
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text or ""
    if result.reason == speechsdk.ResultReason.NoMatch:
        return ""
    if result.reason == speechsdk.ResultReason.Canceled:
        c = result.cancellation_details
        logger.warning("Azure Speech canceled: %s | %s", c.reason, c.error_details)
        return ""
    return ""


# ---------------------------------------------------------------------------
# State-aware tool factory
# ---------------------------------------------------------------------------

# The booking tools live in ``tools/booking.py``. Import them from there:
#     from tools.booking import make_booking_tools
