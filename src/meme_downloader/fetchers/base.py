"""Base fetcher interface for all data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from meme_downloader.db.database import Database, Meme

import hashlib
import mimetypes


@dataclass
class FetchResult:
    """Result of fetching a single meme item."""

    meme: Meme
    image_data: bytes | None = None


class BaseFetcher(ABC):
    """Abstract base class for meme fetchers."""

    name: str = ""

    def __init__(self, db: Database, memes_dir: Path, client: httpx.AsyncClient) -> None:
        self.db = db
        self.memes_dir = memes_dir
        self.client = client

    @abstractmethod
    async def fetch(self, limit: int = 20, **kwargs) -> list[FetchResult]:
        """Fetch meme items from the source. Returns a list of FetchResult."""

    async def save(self, result: FetchResult) -> Meme | None:
        """Save a fetch result: download image, compute hash, store in DB."""
        if result.image_data is None and result.meme.url:
            resp = await self.client.get(result.meme.url, follow_redirects=True)
            resp.raise_for_status()
            result.image_data = resp.content

        if result.image_data is None:
            return None

        hash_hex = hashlib.sha256(result.image_data).hexdigest()

        # Check for duplicate by hash
        existing = await self.db.get_meme_by_hash(hash_hex)
        if existing:
            return None

        # Determine file extension
        ext = _guess_extension(result.meme.url, result.image_data)
        filename = f"{hash_hex}{ext}"

        # Save image file
        filepath = self.memes_dir / filename
        filepath.write_bytes(result.image_data)

        # Save metadata
        result.meme.hash = hash_hex
        result.meme.filename = filename
        await self.db.add_meme(result.meme)

        # Log the fetch for dedup
        if result.meme.source_id:
            await self.db.log_fetch(result.meme.source, result.meme.source_id)

        return result.meme


def _guess_extension(url: str, data: bytes) -> str:
    """Guess file extension from URL or content."""
    # Try from URL
    if url:
        path = url.split("?")[0].split("#")[0]
        for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4"):
            if path.lower().endswith(ext):
                return ext

    # Fallback: check content type signature
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:4] == b"GIF8":
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"

    return ".jpg"  # default
