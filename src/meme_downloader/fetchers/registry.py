"""Fetcher registry - maps source names to fetcher classes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from meme_downloader.db.database import Database
from meme_downloader.fetchers.base import BaseFetcher
from meme_downloader.fetchers.reddit import RedditFetcher
from meme_downloader.fetchers.imgur import ImgurFetcher

_REGISTRY: dict[str, type[BaseFetcher]] = {
    "reddit": RedditFetcher,
    "imgur": ImgurFetcher,
}


def get_fetcher(
    source: str,
    db: Database,
    memes_dir: Path,
    client: httpx.AsyncClient,
    **params: Any,
) -> BaseFetcher:
    """Get a fetcher instance for a given source name."""
    cls = _REGISTRY.get(source)
    if cls is None:
        raise ValueError(f"Unknown source: {source}. Available: {list(_REGISTRY.keys())}")
    return cls(db=db, memes_dir=memes_dir, client=client, **params)


def list_sources() -> list[str]:
    """Return names of all registered sources."""
    return list(_REGISTRY.keys())
