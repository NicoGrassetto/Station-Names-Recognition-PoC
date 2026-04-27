from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Ensure the repo root is importable so ``config`` (top-level package) resolves
# regardless of how the app is launched.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers.config import router as config_router
from src.routers.health import router as health_router
from src.routers.ws import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-12s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("app")

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000"
    ).split(",")
    if o.strip()
]

app = FastAPI(title="Station Names Recognition PoC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(config_router)
app.include_router(ws_router)


