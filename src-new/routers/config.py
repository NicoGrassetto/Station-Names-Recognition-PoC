"""Configuration / metadata endpoints.

Read-only routes the frontend uses to populate UI controls (language picker,
mode selector, model dropdown, etc.). All values come from the existing
``config/`` package and ``custom_speech_endpoints.json`` so there is a single
source of truth.

- ``GET /api/languages``         : supported speech locales.
- ``GET /api/modes``             : conversation mode presets.
- ``GET /api/speech/endpoints``  : Azure Custom Speech endpoint IDs per locale.
- ``GET /api/config``            : everything above bundled into one response.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from config import list_modes, load_session_config

logger = logging.getLogger("config")

router = APIRouter(prefix="/api", tags=["config"])

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SPEECH_ENDPOINTS_PATH = _REPO_ROOT / "config" / "custom_speech_endpoints.json"


def _load_speech_endpoints() -> dict[str, dict[str, str]]:
    try:
        with open(_SPEECH_ENDPOINTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Speech endpoints file not found at %s", _SPEECH_ENDPOINTS_PATH)
        return {}


@router.get("/languages")
async def read_languages() -> dict[str, list[str]]:
    """Locales for which a Custom Speech endpoint is configured."""
    return {"languages": sorted(_load_speech_endpoints().keys())}


@router.get("/models")
async def read_models() -> dict[str, Any]:
    """Available realtime model deployments.

    Sourced from the ``AZURE_OPENAI_DEPLOYMENT`` env var (set by ``azd up``).
    Falls back to a single placeholder entry so the UI dropdown isn't empty.
    """
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-realtime-1-5")
    return {
        "models": [
            {"id": deployment, "model": deployment, "status": "available"}
        ],
        "default": deployment,
    }


@router.get("/modes")
async def read_modes() -> dict[str, list[str]]:
    """Available conversation mode presets (filenames in ``config/modes/``)."""
    return {"modes": list_modes()}


@router.get("/modes/{mode}")
async def read_mode(mode: str) -> dict[str, Any]:
    """Return the merged session config for a given mode."""
    try:
        cfg = load_session_config(mode)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"mode": mode, "session": cfg}


@router.get("/speech/endpoints")
async def read_speech_endpoints() -> dict[str, dict[str, dict[str, str]]]:
    """Azure Custom Speech endpoint IDs and model URLs per locale."""
    return {"endpoints": _load_speech_endpoints()}


@router.get("/config")
async def read_config() -> JSONResponse:
    """One-shot bundle of all read-only metadata, useful at app startup."""
    return JSONResponse(
        {
            "languages": sorted(_load_speech_endpoints().keys()),
            "modes": list_modes(),
            "speech_endpoints": _load_speech_endpoints(),
        }
    )
