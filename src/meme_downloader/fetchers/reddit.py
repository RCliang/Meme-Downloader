"""Reddit meme fetcher using the public JSON API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from meme_downloader.db.database import Meme
from meme_downloader.fetchers.base import BaseFetcher, FetchResult

logger = logging.getLogger(__name__)

# Subreddits focused on memes
DEFAULT_SUBREDDITS = ["memes", "dankmemes", "me_irl", "ProgrammerHumor"]

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


class RedditFetcher(BaseFetcher):
    """Fetch memes from Reddit via public JSON API."""

    name = "reddit"

    def __init__(
        self,
        db,
        memes_dir,
        client: httpx.AsyncClient,
        subreddits: list[str] | None = None,
    ) -> None:
        super().__init__(db, memes_dir, client)
        self.subreddits = subreddits or DEFAULT_SUBREDDITS

    async def fetch(self, limit: int = 20, **kwargs) -> list[FetchResult]:
        subreddits = kwargs.get("subreddits", self.subreddits)
        results: list[FetchResult] = []

        for sub in subreddits:
            sub_results = await self._fetch_subreddit(sub, per_sub=limit)
            results.extend(sub_results)
            if len(results) >= limit:
                break

        return results[:limit]

    async def _fetch_subreddit(self, subreddit: str, per_sub: int = 20) -> list[FetchResult]:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json"
        headers = {"User-Agent": "meme-downloader/0.1"}
        params = {"limit": per_sub}

        try:
            resp = await self.client.get(url, headers=headers, params=params, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Failed to fetch r/%s: %s", subreddit, e)
            return []

        data = resp.json()
        results: list[FetchResult] = []

        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            image_url = self._extract_image_url(post)
            if not image_url:
                continue

            source_id = f"t3_{post.get('id', '')}"

            # Skip already-fetched items
            if await self.db.is_fetched("reddit", source_id):
                continue

            created_utc = post.get("created_utc", 0)
            post_at = datetime.fromtimestamp(created_utc, tz=timezone.utc) if created_utc else None

            meme = Meme(
                source="reddit",
                source_id=source_id,
                title=post.get("title", ""),
                url=image_url,
                post_at=post_at.isoformat() if post_at else None,
            )

            results.append(FetchResult(meme=meme))

        return results

    @staticmethod
    def _extract_image_url(post: dict) -> str | None:
        """Extract the best image URL from a Reddit post."""
        url_overridden = post.get("url_overridden_by_dest", "")
        if url_overridden and any(url_overridden.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
            return url_overridden

        # Check preview images
        preview = post.get("preview", {}).get("images", [])
        if preview:
            source = preview[0].get("source", {})
            url = source.get("url", "")
            # Reddit preview URLs use amp; encoding
            return url.replace("&amp;", "&") if url else None

        return None
