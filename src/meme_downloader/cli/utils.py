"""Shared utilities for CLI commands."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import AsyncIterator

import httpx

from meme_downloader.config import Config
from meme_downloader.db.database import Database


@contextlib.asynccontextmanager
async def db_session(config: Config | None = None) -> AsyncIterator[Database]:
    """Provide an initialized database session."""
    config = config or Config.load()
    config.ensure_dirs()
    db = Database(config.db_path)
    await db.connect()
    try:
        yield db
    finally:
        await db.close()


def get_http_client() -> httpx.AsyncClient:
    """Return a pre-configured httpx client."""
    return httpx.AsyncClient(timeout=30.0, follow_redirects=True)
