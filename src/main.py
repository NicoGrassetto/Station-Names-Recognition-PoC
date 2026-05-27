from __future__ import annotations

import json
import logging
import os
import struct
import sys
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from azure.identity import DefaultAzureCredential

# Allow imports from project root (config/, prompts/, tools/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import list_modes
from src.providers import (
    DEFAULT_PROVIDER,
    ConversationProviderConfig,
    ProviderUnavailableError,
    get_provider,
    list_provider_metadata,
    total_active_count,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("realtime-relay")

load_dotenv()

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000"
    ).split(",")
    if o.strip()
]
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "10"))
DEFAULT_CONVERSATION_PROVIDER = os.getenv("CONVERSATION_PROVIDER", DEFAULT_PROVIDER)
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-realtime-1-5")
AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID", "")
AZURE_RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP", "")
AZURE_AI_RESOURCE_NAME = os.getenv("AZURE_AI_RESOURCE_NAME", "")
# Max audio samples per WebSocket message (~20 s at 24 kHz mono 16-bit)
_MAX_AUDIO_SAMPLES = 960_000

app = FastAPI(title="GPT Realtime Starter Kit")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

_credential = DefaultAzureCredential()


def _get_azure_token() -> str:
    token = _credential.get_token("https://cognitiveservices.azure.com/.default")
    return token.token


def _get_arm_token() -> str:
    token = _credential.get_token("https://management.azure.com/.default")
    return token.token


def _configured_model_response(error: str | None = None) -> JSONResponse:
    payload: dict[str, object] = {
        "models": [
            {
                "id": AZURE_OPENAI_DEPLOYMENT,
                "model": AZURE_OPENAI_DEPLOYMENT,
                "status": "configured" if error is None else "unknown",
            }
        ],
        "default": AZURE_OPENAI_DEPLOYMENT,
    }
    if error:
        payload["warning"] = error
    return JSONResponse(payload)


def _infer_ai_resource_name() -> str:
    if AZURE_AI_RESOURCE_NAME:
        return AZURE_AI_RESOURCE_NAME
    if not AZURE_OPENAI_ENDPOINT:
        return ""
    host = urlparse(AZURE_OPENAI_ENDPOINT).hostname or ""
    return host.split(".", 1)[0]


async def _send_ws_error(websocket: WebSocket, error: str) -> None:
    try:
        await websocket.accept()
    except RuntimeError:
        pass
    try:
        await websocket.send_text(json.dumps({"type": "error", "error": error}))
    finally:
        await websocket.close()


@app.get("/health")
async def health():
    try:
        _get_azure_token()
        return JSONResponse({"status": "ok"})
    except Exception:
        logger.exception("Health check failed")
        return JSONResponse(
            {"status": "error", "detail": "Health check failed"}, status_code=500
        )


@app.get("/api/modes")
async def get_modes():
    return JSONResponse({"modes": list_modes()})


@app.get("/api/providers")
async def get_providers():
    return JSONResponse(
        {
            "providers": list_provider_metadata(),
            "default": DEFAULT_CONVERSATION_PROVIDER,
        }
    )


@app.get("/api/models")
async def get_models():
    """List configured Azure AI model deployments when ARM identifiers exist."""
    resource_name = _infer_ai_resource_name()
    if not (AZURE_SUBSCRIPTION_ID and AZURE_RESOURCE_GROUP and resource_name):
        return _configured_model_response()

    try:
        token = _get_arm_token()
        url = (
            "https://management.azure.com"
            f"/subscriptions/{AZURE_SUBSCRIPTION_ID}"
            f"/resourceGroups/{AZURE_RESOURCE_GROUP}"
            f"/providers/Microsoft.CognitiveServices/accounts/{resource_name}"
            "/deployments?api-version=2024-10-01"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

        models = []
        for dep in data.get("value", []):
            model = dep.get("properties", {}).get("model", {})
            models.append(
                {
                    "id": dep.get("name", ""),
                    "model": model.get("name", ""),
                    "status": dep.get("properties", {}).get("provisioningState", ""),
                }
            )

        models.sort(
            key=lambda m: (0 if m["id"] == AZURE_OPENAI_DEPLOYMENT else 1, m["id"])
        )

        return JSONResponse({"models": models, "default": AZURE_OPENAI_DEPLOYMENT})
    except Exception as exc:
        logger.warning("Failed to list model deployments via ARM: %s", exc)
        return _configured_model_response("Failed to list deployments via ARM")


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    mode: str = "booking",
    model: str | None = None,
    provider: str | None = None,
    provider_route: str | None = None,
):
    provider_id = provider or DEFAULT_CONVERSATION_PROVIDER
    logger.info(
        "Client connecting - session=%s, mode=%s, model=%s, provider=%s, route=%s",
        session_id,
        mode,
        model or "default",
        provider_id,
        provider_route or "default",
    )

    try:
        conversation_provider = get_provider(provider_id)
    except ValueError as exc:
        await _send_ws_error(websocket, str(exc))
        return
    except ProviderUnavailableError as exc:
        await _send_ws_error(websocket, str(exc))
        return

    if total_active_count() >= MAX_SESSIONS:
        await _send_ws_error(websocket, "Maximum concurrent sessions reached")
        return

    config = ConversationProviderConfig(
        mode=mode,
        model=model,
        route=provider_route,
    )

    try:
        await conversation_provider.connect(websocket, session_id, config)
    except FileNotFoundError as e:
        await conversation_provider.disconnect(session_id)
        await _send_ws_error(websocket, str(e))
        return
    except ValueError as e:
        await conversation_provider.disconnect(session_id)
        await _send_ws_error(websocket, str(e))
        return
    except NotImplementedError as e:
        await conversation_provider.disconnect(session_id)
        await _send_ws_error(websocket, str(e))
        return
    except Exception:
        logger.exception("Failed to connect session %s", session_id)
        await conversation_provider.disconnect(session_id)
        await _send_ws_error(websocket, "Connection failed")
        return

    logger.info("Session %s connected via provider %s", session_id, provider_id)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from session %s", session_id)
                continue

            msg_type = message.get("type")

            if msg_type == "audio":
                int16_data = message.get("data", [])
                if (
                    not isinstance(int16_data, list)
                    or len(int16_data) > _MAX_AUDIO_SAMPLES
                ):
                    logger.warning(
                        "Audio payload too large or invalid from session %s",
                        session_id,
                    )
                    continue
                audio_bytes = struct.pack(f"{len(int16_data)}h", *int16_data)
                await conversation_provider.send_audio(session_id, audio_bytes)

            elif msg_type == "commit_audio":
                await conversation_provider.commit_audio(session_id)

            elif msg_type == "interrupt":
                await conversation_provider.interrupt(session_id)

            elif msg_type == "text":
                text = message.get("text", "")
                if text:
                    await conversation_provider.send_text(session_id, text)

    except WebSocketDisconnect:
        logger.info("Client disconnected - session=%s", session_id)
    except Exception as e:
        logger.exception("WebSocket error for session %s: %s", session_id, e)
    finally:
        await conversation_provider.disconnect(session_id)
        logger.info("Session %s cleaned up", session_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
