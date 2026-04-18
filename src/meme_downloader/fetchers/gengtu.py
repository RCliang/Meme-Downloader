"""gengtu.net meme fetcher using cloudscraper for Cloudflare bypass."""

from __future__ import annotations

import asyncio
import logging
import random
import re

import httpx

from meme_downloader.db.database import Meme
from meme_downloader.fetchers.base import BaseFetcher, FetchResult

logger = logging.getLogger(__name__)

BASE_URL = "https://gengtu.net"

_CARD_START_RE = re.compile(r'data-meme-id="(\d+)"')
_IMG_SRC_RE = re.compile(r'<img\s+[^>]*src="([^"]+)"')
_TITLE_RE = re.compile(r'<h2[^>]*class="[^"]*card-title[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>')
_DESC_RE = re.compile(r'<p[^>]*class="[^"]*text-sm text-gray-500[^"]*"[^>]*>([^<]+)</p>')

# Volcengine TOS image processing param — strip for original quality
_IMAGE_PROCESS_SUFFIX = "?x-tos-process=style/c"


class GengtuFetcher(BaseFetcher):
    """Fetch memes from gengtu.net via HTML scraping."""

    name = "gengtu"

    async def fetch(self, limit: int = 20, **kwargs) -> list[FetchResult]:
        seed = kwargs.get("seed", random.randint(1, 99999))
        url = f"{BASE_URL}/memes/random/{seed}/"

        html = await asyncio.to_thread(self._fetch_html, url)
        if not html:
            return []

        cards = self._parse_cards(html)
        if not cards:
            logger.warning("Parsed 0 cards from gengtu.net (page may have changed)")

        results: list[FetchResult] = []
        for source_id, title, image_url, _description in cards:
            if await self.db.is_fetched("gengtu", source_id):
                continue

            meme = Meme(
                source="gengtu",
                source_id=source_id,
                title=title,
                url=image_url,
            )
            results.append(FetchResult(meme=meme))
            if len(results) >= limit:
                break

        return results

    @staticmethod
    def _fetch_html(url: str) -> str:
        import cloudscraper

        scraper = cloudscraper.create_scraper()
        try:
            resp = scraper.get(url, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.warning("Failed to fetch gengtu.net page %s: %s", url, e)
            return ""

    @staticmethod
    def _parse_cards(html: str) -> list[tuple[str, str, str, str]]:
        results: list[tuple[str, str, str, str]] = []

        for match in _CARD_START_RE.finditer(html):
            source_id = match.group(1)
            chunk = html[match.start() : match.start() + 3000]

            img_match = _IMG_SRC_RE.search(chunk)
            if not img_match:
                continue
            image_url = img_match.group(1).split("?")[0]

            title_match = _TITLE_RE.search(chunk)
            title = title_match.group(1).strip() if title_match else ""

            desc_match = _DESC_RE.search(chunk)
            description = desc_match.group(1).strip() if desc_match else ""

            results.append((source_id, title, image_url, description))

        return results
