"""Milvus vector store for meme similarity search."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from meme_downloader.config import MilvusConfig

logger = logging.getLogger(__name__)


@dataclass
class SimilarityResult:
    """A single similarity search result."""

    meme_id: int
    source: str
    score: float


class MilvusStore:
    """Manages Milvus collection for meme embeddings."""

    def __init__(self, config: MilvusConfig, dimensions: int = 1024) -> None:
        self._config = config
        self._dimensions = dimensions
        self._collection: Collection | None = None

    def connect(self) -> None:
        """Connect to Milvus and ensure collection exists."""
        connections.connect(
            alias="default",
            uri=self._config.uri,
            token=self._config.token or None,
        )
        self._ensure_collection()

    def disconnect(self) -> None:
        """Disconnect from Milvus."""
        connections.disconnect("default")
        self._collection = None

    def _ensure_collection(self) -> None:
        """Create collection and index if they don't exist."""
        name = self._config.collection
        if utility.has_collection(name):
            self._collection = Collection(name)
            self._collection.load()
            return

        fields = [
            FieldSchema(name="meme_id", dtype=DataType.INT64, is_primary=True),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=self._dimensions,
            ),
        ]
        schema = CollectionSchema(fields, description="Meme description embeddings")
        self._collection = Collection(name, schema=schema)

        if self._config.index_type == "HNSW":
            index_params = {
                "metric_type": "COSINE",
                "index_type": "HNSW",
                "params": {"M": 16, "efConstruction": 256},
            }
        else:
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            }

        self._collection.create_index(field_name="embedding", index_params=index_params)
        self._collection.load()
        logger.info("Created Milvus collection '%s' (dim=%d, index=%s)", name, self._dimensions, self._config.index_type)

    def upsert(self, meme_id: int, source: str, embedding: list[float]) -> None:
        """Insert or update a meme embedding."""
        self._require_collection()
        self._collection.upsert([[meme_id], [source], [embedding]])

    def upsert_batch(
        self,
        meme_ids: list[int],
        sources: list[str],
        embeddings: list[list[float]],
    ) -> None:
        """Batch upsert multiple embeddings."""
        self._require_collection()
        self._collection.upsert([meme_ids, sources, embeddings])

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        source: str = "",
    ) -> list[SimilarityResult]:
        """Search for similar embeddings."""
        self._require_collection()

        if self._config.index_type == "HNSW":
            search_params = {"metric_type": "COSINE", "params": {"ef": top_k * 2}}
        else:
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}

        expr = f'source == "{source}"' if source else ""

        results = self._collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["meme_id", "source"],
        )

        similarity_results: list[SimilarityResult] = []
        for hits in results:
            for hit in hits:
                similarity_results.append(
                    SimilarityResult(
                        meme_id=hit.entity.get("meme_id"),
                        source=hit.entity.get("source"),
                        score=hit.score,
                    )
                )
        return similarity_results

    def delete(self, meme_id: int) -> None:
        """Delete a meme's embedding."""
        self._require_collection()
        self._collection.delete(f"meme_id == {meme_id}")

    def count(self) -> int:
        """Return the number of embeddings in the collection."""
        if self._collection is None:
            return 0
        self._collection.flush()
        return self._collection.num_entities

    def _require_collection(self) -> None:
        if self._collection is None:
            raise RuntimeError("Not connected. Call connect() first.")
