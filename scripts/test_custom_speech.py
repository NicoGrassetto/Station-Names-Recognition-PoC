#!/usr/bin/env python3
"""Test a custom Speech endpoint on a local WAV file.

Usage:
  python3 scripts/test_custom_speech.py <locale> <audio.wav>
  python3 scripts/test_custom_speech.py en-US data/en-US/audio/clip006.wav
  python3 scripts/test_custom_speech.py fr-FR data/fr-FR/audio/clip001.wav

Compares custom endpoint result vs base model for the same locale.
Auth: AAD via DefaultAzureCredential.
"""
import json
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
import azure.cognitiveservices.speech as speechsdk

ROOT = Path(__file__).resolve().parent.parent


def env(k: str) -> str:
    v = os.getenv(k)
    if not v:
        sys.exit(f"Missing env var: {k}")
    return v


def make_speech_config(use_endpoint_id: Optional[str], locale: str) -> speechsdk.SpeechConfig:
    region = env("AZURE_SPEECH_REGION")
    sub_id = env("AZURE_SUBSCRIPTION_ID")
    rg = env("AZURE_RESOURCE_GROUP")
    name = env("AZURE_SPEECH_RESOURCE_NAME")
    resource_id = (
        f"/subscriptions/{sub_id}/resourceGroups/{rg}"
        f"/providers/Microsoft.CognitiveServices/accounts/{name}"
    )
    token = DefaultAzureCredential().get_token(
        "https://cognitiveservices.azure.com/.default"
    ).token
    auth_token = f"aad#{resource_id}#{token}"
    cfg = speechsdk.SpeechConfig(auth_token=auth_token, region=region)
    cfg.speech_recognition_language = locale
    if use_endpoint_id:
        cfg.endpoint_id = use_endpoint_id
    return cfg


def recognize(cfg: speechsdk.SpeechConfig, audio_path: Path) -> str:
    audio_in = speechsdk.audio.AudioConfig(filename=str(audio_path))
    rec = speechsdk.SpeechRecognizer(speech_config=cfg, audio_config=audio_in)
    result = rec.recognize_once()
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    if result.reason == speechsdk.ResultReason.NoMatch:
        return "<no match>"
    if result.reason == speechsdk.ResultReason.Canceled:
        c = result.cancellation_details
        return f"<canceled: {c.reason} | {c.error_details}>"
    return f"<unexpected: {result.reason}>"


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    locale, audio_arg = sys.argv[1], sys.argv[2]
    audio_path = Path(audio_arg)
    if not audio_path.exists():
        sys.exit(f"Audio file not found: {audio_path}")

    load_dotenv(ROOT / ".env")
    manifest_path = ROOT / "config" / "custom_speech_endpoints.json"
    if not manifest_path.exists():
        sys.exit(f"Manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if locale not in manifest:
        sys.exit(f"Locale {locale} not in manifest. Available: {list(manifest)}")
    endpoint_id = manifest[locale]["endpoint_id"]

    print(f"File:   {audio_path}")
    print(f"Locale: {locale}")
    transcript_path = audio_path.with_suffix(".txt")
    if transcript_path.exists():
        print(f"Truth:  {transcript_path.read_text().strip()}")
    print()

    print("Custom endpoint  ...", flush=True, end=" ")
    custom = recognize(make_speech_config(endpoint_id, locale), audio_path)
    print(custom)

    print("Base model       ...", flush=True, end=" ")
    base = recognize(make_speech_config(None, locale), audio_path)
    print(base)


if __name__ == "__main__":
    main()
