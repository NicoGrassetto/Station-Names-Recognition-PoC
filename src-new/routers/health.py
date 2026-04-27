"""Health and operational endpoints.

These are app-level routes used by load balancers, container orchestrators
(e.g. Azure Container Apps, Kubernetes), and humans debugging deploys.

- ``GET /``        : trivial root, returns ``{"status": "ok"}``.
- ``GET /health``  : **liveness** — process is up and serving requests.
- ``GET /ready``   : **readiness** — upstream dependencies (Azure creds)
                     are reachable; safe to send traffic.
- ``GET /version`` : build metadata (commit SHA, version) for debugging.

See https://fastapi.tiangolo.com/tutorial/bigger-applications/.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger("health")

router = APIRouter(tags=["health"])


@router.get("/")
async def read_root() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health")
async def read_health() -> dict[str, str]:
    """Liveness probe — the process is running."""
    return {"status": "ok"}


@router.get("/ready")
async def read_ready() -> JSONResponse:
    """Readiness probe — verify we can acquire an Azure AD token.

    Returns 200 when dependencies look healthy, 503 otherwise so that
    orchestrators stop routing traffic until the issue is resolved.
    """
    try:
        # Imported lazily so a missing azure-identity install doesn't break
        # the rest of the app at import time.
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        credential.get_token("https://cognitiveservices.azure.com/.default")
        return JSONResponse({"status": "ready"})
    except Exception:
        logger.exception("Readiness check failed")
        return JSONResponse(
            {"status": "not_ready", "detail": "dependency_check_failed"},
            status_code=503,
        )


@router.get("/version")
async def read_version() -> dict[str, str]:
    """Build metadata. Values come from env vars set at deploy time."""
    return {
        "version": os.getenv("APP_VERSION", "dev"),
        "commit": os.getenv("GIT_COMMIT", "unknown"),
    }
