"""Shared utilities for CLI commands."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from meme_downloader.config import Config
from meme_downloader.db.database import Database


def is_vector_enabled(config: Config) -> bool:
    """Check if vector search is fully configured."""
    vc = config.vector
    return vc.enabled and bool(vc.embedding.api_key) and bool(vc.milvus.uri)


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


@contextlib.asynccontextmanager
async def vector_store(config: Config | None = None) -> AsyncIterator[Any]:
    """Provide a connected Milvus store (yields None if not configured)."""
    config = config or Config.load()
    if not is_vector_enabled(config):
        yield None
        return

    from meme_downloader.vector.store import MilvusStore

    store = MilvusStore(config.vector.milvus, dimensions=config.vector.embedding.dimensions)
    try:
        await asyncio.to_thread(store.connect)
        yield store
    finally:
        try:
            await asyncio.to_thread(store.disconnect)
        except Exception:
            pass


def get_http_client() -> httpx.AsyncClient:
    """Return a pre-configured httpx client."""
    return httpx.AsyncClient(timeout=30.0, follow_redirects=True)
