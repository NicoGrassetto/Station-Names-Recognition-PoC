"""Conversation provider registry."""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass

from src.providers.base import ConversationProvider, ConversationProviderConfig

DEFAULT_PROVIDER = "gpt-realtime"

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
NOT_IMPLEMENTED = "not_implemented"


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    module: str
    class_name: str
    default_status: str = AVAILABLE
    default_reason: str | None = None


class ProviderUnavailableError(RuntimeError):
    """Raised when a known provider cannot be loaded or used."""


_PROVIDER_SPECS: dict[str, ProviderSpec] = {
    DEFAULT_PROVIDER: ProviderSpec(
        id=DEFAULT_PROVIDER,
        name="GPT Realtime",
        module="src.providers.gpt_realtime",
        class_name="GPTRealtimeProvider",
    ),
    "voice-live": ProviderSpec(
        id="voice-live",
        name="Voice Live",
        module="src.providers.voice_live",
        class_name="VoiceLiveProvider",
        default_status=NOT_IMPLEMENTED,
        default_reason="Voice Live routes are scaffolded but not implemented yet.",
    ),
}

_PROVIDERS: dict[str, ConversationProvider] = {}

_ALIASES = {
    "realtime": DEFAULT_PROVIDER,
    "gpt_realtime": DEFAULT_PROVIDER,
    "voice_live": "voice-live",
}


def _normalize_provider_id(provider_id: str | None) -> str:
    normalized = (provider_id or DEFAULT_PROVIDER).strip().lower()
    return _ALIASES.get(normalized, normalized)


def _load_provider(spec: ProviderSpec) -> ConversationProvider:
    if spec.id in _PROVIDERS:
        return _PROVIDERS[spec.id]
    try:
        module = importlib.import_module(spec.module)
        provider_cls = getattr(module, spec.class_name)
        provider: ConversationProvider = provider_cls()
    except Exception as exc:
        reason = f"{spec.name} provider could not be loaded: {type(exc).__name__}: {exc}"
        if type(exc).__name__ == "KeyError" and "~TContext" in str(exc):
            reason = (
                f"{reason}. This is a known local runtime issue with openai-agents "
                f"on Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}; "
                "use a newer Python 3.11 patch release or Python 3.12+."
            )
        raise ProviderUnavailableError(
            reason
        ) from exc
    _PROVIDERS[spec.id] = provider
    return provider


def get_provider(provider_id: str | None) -> ConversationProvider:
    normalized = _normalize_provider_id(provider_id)
    try:
        spec = _PROVIDER_SPECS[normalized]
    except KeyError as exc:
        raise ValueError(
            f"Unknown provider '{provider_id}'. Available: {sorted(_PROVIDER_SPECS)}"
        ) from exc
    return _load_provider(spec)


def total_active_count() -> int:
    total = 0
    for provider in _PROVIDERS.values():
        total += provider.active_count()
    return total


def list_provider_metadata() -> list[dict[str, object]]:
    providers: list[dict[str, object]] = []
    for provider_id, spec in _PROVIDER_SPECS.items():
        entry: dict[str, object] = {
            "id": provider_id,
            "name": spec.name,
            "status": spec.default_status,
            "disabled": spec.default_status != AVAILABLE,
        }
        if spec.default_reason:
            entry["reason"] = spec.default_reason
        try:
            provider = _load_provider(spec)
        except ProviderUnavailableError as exc:
            entry.update(
                {
                    "status": UNAVAILABLE,
                    "disabled": True,
                    "reason": str(exc),
                }
            )
            providers.append(entry)
            continue

        route_metadata = getattr(provider, "route_metadata", None)
        if callable(route_metadata):
            entry["routes"] = route_metadata()
        status_metadata = getattr(provider, "status_metadata", None)
        if callable(status_metadata):
            entry.update(status_metadata())
        providers.append(entry)
    return providers
