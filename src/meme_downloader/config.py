"""Configuration management for Meme Downloader."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def get_default_data_dir() -> Path:
    """Return the default data directory (~/.meme-downloader)."""
    return Path.home() / ".meme-downloader"


@dataclass
class SourceConfig:
    """Configuration for a single data source."""

    name: str
    enabled: bool = True
    params: dict = field(default_factory=dict)


@dataclass
class EmbeddingConfig:
    """Configuration for the embedding API."""

    api_key: str = ""
    model: str = "text-embedding-v3"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dimensions: int = 1024
    batch_size: int = 20


@dataclass
class MilvusConfig:
    """Configuration for the Milvus vector database."""

    uri: str = "http://localhost:19530"
    token: str = ""
    collection: str = "meme_embeddings"
    index_type: str = "HNSW"


@dataclass
class VectorConfig:
    """Top-level vector search configuration."""

    enabled: bool = False
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    milvus: MilvusConfig = field(default_factory=MilvusConfig)


@dataclass
class Config:
    """Application configuration."""

    data_dir: Path = field(default_factory=get_default_data_dir)
    sources: list[SourceConfig] = field(default_factory=list)
    vector: VectorConfig = field(default_factory=VectorConfig)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "metadata.db"

    @property
    def memes_dir(self) -> Path:
        return self.data_dir / "memes"

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.yaml"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    def ensure_dirs(self) -> None:
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.memes_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load configuration from a YAML file."""
        path = path or get_default_data_dir() / "config.yaml"
        if not path.exists():
            return cls()

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        sources = [
            SourceConfig(name=s["name"], enabled=s.get("enabled", True), params=s.get("params", {}))
            for s in data.get("sources", [])
        ]

        vector_data = data.get("vector", {})
        emb_data = vector_data.get("embedding", {})
        mil_data = vector_data.get("milvus", {})
        vector = VectorConfig(
            enabled=vector_data.get("enabled", False),
            embedding=EmbeddingConfig(
                api_key=emb_data.get("api_key", ""),
                model=emb_data.get("model", "text-embedding-v3"),
                base_url=emb_data.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                dimensions=emb_data.get("dimensions", 1024),
                batch_size=emb_data.get("batch_size", 20),
            ),
            milvus=MilvusConfig(
                uri=mil_data.get("uri", "http://localhost:19530"),
                token=mil_data.get("token", ""),
                collection=mil_data.get("collection", "meme_embeddings"),
                index_type=mil_data.get("index_type", "HNSW"),
            ),
        )

        data_dir = Path(data["data_dir"]) if "data_dir" in data else get_default_data_dir()
        return cls(data_dir=data_dir, sources=sources, vector=vector)

    def save(self, path: Path | None = None) -> None:
        """Save configuration to a YAML file."""
        path = path or self.config_path
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "data_dir": str(self.data_dir),
            "sources": [
                {"name": s.name, "enabled": s.enabled, **s.params}
                for s in self.sources
            ],
            "vector": {
                "enabled": self.vector.enabled,
                "embedding": {
                    "api_key": self.vector.embedding.api_key,
                    "model": self.vector.embedding.model,
                    "base_url": self.vector.embedding.base_url,
                    "dimensions": self.vector.embedding.dimensions,
                    "batch_size": self.vector.embedding.batch_size,
                },
                "milvus": {
                    "uri": self.vector.milvus.uri,
                    "token": self.vector.milvus.token,
                    "collection": self.vector.milvus.collection,
                    "index_type": self.vector.milvus.index_type,
                },
            },
        }

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
