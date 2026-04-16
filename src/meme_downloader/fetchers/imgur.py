"""Imgur meme fetcher using the public gallery API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from meme_downloader.db.database import Meme
from meme_downloader.fetchers.base import BaseFetcher, FetchResult

logger = logging.getLogger(__name__)

GALLERY_ENDPOINT = "https://api.imgur.com/3/gallery/search/viral"


class ImgurFetcher(BaseFetcher):
    """Fetch memes from Imgur via public API."""

    name = "imgur"

    def __init__(
        self,
        db,
        memes_dir,
        client: httpx.AsyncClient,
        client_id: str = "",
    ) -> None:
        super().__init__(db, memes_dir, client)
        self.client_id = client_id

    async def fetch(self, limit: int = 20, **kwargs) -> list[FetchResult]:
        if not self.client_id:
            logger.warning("Imgur client_id not configured, skipping")
            return []

        headers = {"Authorization": f"Client-ID {self.client_id}"}
        results: list[FetchResult] = []

        # Search for viral meme content
        for query in ["memes", "funny"]:
            params = {"q": query, "sort": "viral", "page": 0}
            try:
                resp = await self.client.get(
                    GALLERY_ENDPOINT, headers=headers, params=params, follow_redirects=True
                )
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.warning("Failed to fetch Imgur (%s): %s", query, e)
                continue

            data = resp.json()
            for item in data.get("data", []):
                if item.get("is_album"):
                    # For albums, use the first image
                    images = item.get("images", [])
                    if not images:
                        continue
                    img = images[0]
                else:
                    img = item

                image_url = img.get("link", "")
                if not image_url or not image_url.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                    continue

                source_id = item.get("id", "")
                if await self.db.is_fetched("imgur", source_id):
                    continue

                post_time = item.get("datetime", 0)
                post_at = datetime.fromtimestamp(post_time, tz=timezone.utc) if post_time else None

                meme = Meme(
                    source="imgur",
                    source_id=source_id,
                    title=item.get("title", ""),
                    url=image_url,
                    post_at=post_at.isoformat() if post_at else None,
                )
                results.append(FetchResult(meme=meme))

                if len(results) >= limit:
                    return results[:limit]

        return results[:limit]
