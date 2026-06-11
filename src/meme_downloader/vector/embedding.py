"""Embedding generation via OpenAI-compatible API (DashScope)."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from meme_downloader.config import EmbeddingConfig

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Async wrapper for generating text embeddings."""

    def __init__(self, config: EmbeddingConfig) -> None:
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )
        self._model = config.model
        self._dimensions = config.dimensions
        self._batch_size = config.batch_size

    async def embed_text(self, text: str) -> list[float] | None:
        """Generate embedding for a single text string."""
        if not text.strip():
            return None
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=text,
                dimensions=self._dimensions,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("Failed to generate embedding: %s", e)
            return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for a batch of texts."""
        results: list[list[float] | None] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            valid_indices = [j for j, t in enumerate(batch) if t.strip()]
            if not valid_indices:
                results.extend([None] * len(batch))
                continue

            valid_texts = [batch[j] for j in valid_indices]
            try:
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=valid_texts,
                    dimensions=self._dimensions,
                )
                embeddings_by_index = {
                    idx: response.data[k].embedding
                    for k, idx in enumerate(valid_indices)
                }
                for j in range(len(batch)):
                    results.append(embeddings_by_index.get(j))
            except Exception as e:
                logger.error("Batch embedding failed at offset %d: %s", i, e)
                results.extend([None] * len(batch))

        return results
