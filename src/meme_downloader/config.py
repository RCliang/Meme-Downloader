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
class Config:
    """Application configuration."""

    data_dir: Path = field(default_factory=get_default_data_dir)
    sources: list[SourceConfig] = field(default_factory=list)

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

        data_dir = Path(data["data_dir"]) if "data_dir" in data else get_default_data_dir()
        return cls(data_dir=data_dir, sources=sources)

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
        }

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
