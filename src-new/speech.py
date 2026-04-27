"""Azure Custom Speech bridge for the destination-selection step.

We deliberately do **not** use Whisper here: station names (especially
Belgian/French ones) are recognized by a custom Azure Speech endpoint
that has been fine-tuned on the NMBS station vocabulary. The endpoint
ids per locale live in :file:`config/custom_speech_endpoints.json`.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

import azure.cognitiveservices.speech as speechsdk
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("speech")

_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _ROOT / "config" / "custom_speech_endpoints.json"

_credential = DefaultAzureCredential()


def get_speech_endpoint_id(locale: str) -> Optional[str]:
    """Return the custom Speech endpoint id configured for ``locale``."""
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

    endpoint_id = get_speech_endpoint_id(locale)
    if endpoint_id:
        cfg.endpoint_id = endpoint_id
        logger.info("speech endpoint %s -> %s", locale, endpoint_id)
    else:
        logger.warning("no custom endpoint for locale %s, using base model", locale)
    return cfg


def transcribe_destination_audio(
    pcm16: bytes,
    locale: str,
    sample_rate: int = 16000,
) -> str:
    """Transcribe a raw PCM16 mono buffer via the custom Azure Speech endpoint."""
    if not pcm16:
        logger.info("transcribe: empty buffer, skipping")
        return ""

    logger.info(
        "Azure Speech: transcribing %d bytes (locale=%s, sr=%d)",
        len(pcm16),
        locale,
        sample_rate,
    )

    cfg = _make_speech_config(locale)
    fmt = speechsdk.audio.AudioStreamFormat(
        samples_per_second=sample_rate, bits_per_sample=16, channels=1
    )
    push = speechsdk.audio.PushAudioInputStream(stream_format=fmt)
    audio_in = speechsdk.audio.AudioConfig(stream=push)

    rec = speechsdk.SpeechRecognizer(speech_config=cfg, audio_config=audio_in)
    push.write(pcm16)
    push.close()

    result = rec.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        text = result.text or ""
        logger.info("Azure Speech: recognized %r", text)
        return text
    if result.reason == speechsdk.ResultReason.NoMatch:
        logger.info("Azure Speech: no match")
        return ""
    if result.reason == speechsdk.ResultReason.Canceled:
        c = result.cancellation_details
        logger.warning("Azure Speech: canceled (%s) %s", c.reason, c.error_details)
        return ""
    return ""
