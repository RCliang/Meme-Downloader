"""SQLite database layer for Meme Downloader."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    source TEXT NOT NULL,
    source_id TEXT,
    title TEXT,
    url TEXT,
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    post_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memes_hash ON memes(hash);
CREATE INDEX IF NOT EXISTS idx_memes_source ON memes(source);
CREATE INDEX IF NOT EXISTS idx_memes_title ON memes(title);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS meme_tags (
    meme_id INTEGER NOT NULL REFERENCES memes(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (meme_id, tag_id)
);

CREATE TABLE IF NOT EXISTS fetch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
);
"""


@dataclass
class Meme:
    """Represents a single meme record."""

    id: int | None = None
    hash: str = ""
    filename: str = ""
    source: str = ""
    source_id: str = ""
    title: str = ""
    url: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    created_at: datetime | None = None
    post_at: datetime | None = None


class Database:
    """Async SQLite database interface."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open the database connection and ensure schema exists."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        await self._migrate()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    # ── Meme CRUD ──────────────────────────────────────────────

    async def _migrate(self) -> None:
        """Run lightweight migrations for schema changes."""
        try:
            await self.conn.execute("SELECT description FROM memes LIMIT 0")
        except aiosqlite.OperationalError:
            await self.conn.execute("ALTER TABLE memes ADD COLUMN description TEXT DEFAULT ''")
            await self.conn.commit()

    async def add_meme(self, meme: Meme) -> int:
        """Insert a meme record. Returns the row id."""
        tags_json = json.dumps(meme.tags, ensure_ascii=False)
        cursor = await self.conn.execute(
            """INSERT OR IGNORE INTO memes (hash, filename, source, source_id, title, url, tags, post_at, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (meme.hash, meme.filename, meme.source, meme.source_id, meme.title, meme.url, tags_json, meme.post_at, meme.description),
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def get_meme_by_hash(self, hash: str) -> Meme | None:
        """Look up a meme by its SHA256 hash."""
        row = await self.conn.execute_fetchall(
            "SELECT * FROM memes WHERE hash = ?", (hash,)
        )
        return self._row_to_meme(row[0]) if row else None

    async def get_meme_by_id(self, id: int) -> Meme | None:
        """Look up a meme by its numeric id."""
        row = await self.conn.execute_fetchall(
            "SELECT * FROM memes WHERE id = ?", (id,)
        )
        return self._row_to_meme(row[0]) if row else None

    async def search_memes(
        self,
        keyword: str = "",
        source: str = "",
        tag: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> list[Meme]:
        """Search memes by keyword, source, and/or tag."""
        query = "SELECT m.* FROM memes m"
        params: list[Any] = []
        conditions: list[str] = []

        if tag:
            query += " JOIN meme_tags mt ON m.id = mt.meme_id JOIN tags t ON mt.tag_id = t.id"
            conditions.append("t.name = ?")
            params.append(tag)

        if keyword:
            conditions.append("m.title LIKE ?")
            params.append(f"%{keyword}%")

        if source:
            conditions.append("m.source = ?")
            params.append(source)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY m.created_at DESC LIMIT {int(limit)} OFFSET {int(offset)}"
        rows = await self.conn.execute_fetchall(query, params)
        return [self._row_to_meme(r) for r in rows]

    async def random_memes(self, tag: str = "", count: int = 1) -> list[Meme]:
        """Get random memes, optionally filtered by tag."""
        query = "SELECT m.* FROM memes m"
        params: list[Any] = []

        if tag:
            query += " JOIN meme_tags mt ON m.id = mt.meme_id JOIN tags t ON mt.tag_id = t.id"
            query += " WHERE t.name = ?"
            params.append(tag)

        query += f" ORDER BY RANDOM() LIMIT {int(count)}"
        rows = await self.conn.execute_fetchall(query, params)
        return [self._row_to_meme(r) for r in rows]

    async def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics."""
        total = (await self.conn.execute_fetchall("SELECT COUNT(*) as c FROM memes"))[0]["c"]
        by_source = await self.conn.execute_fetchall(
            "SELECT source, COUNT(*) as c FROM memes GROUP BY source ORDER BY c DESC"
        )
        tag_count = (await self.conn.execute_fetchall("SELECT COUNT(*) as c FROM tags"))[0]["c"]
        return {
            "total_memes": total,
            "total_tags": tag_count,
            "by_source": {r["source"]: r["c"] for r in by_source},
        }

    # ── Tags ───────────────────────────────────────────────────

    async def get_memes_with_descriptions(
        self, source: str = "", limit: int = 100
    ) -> list[Meme]:
        """Get memes that have descriptions (for vector indexing)."""
        query = "SELECT * FROM memes WHERE description != '' AND description IS NOT NULL"
        params: list[Any] = []
        if source:
            query += " AND source = ?"
            params.append(source)
        query += f" ORDER BY id ASC LIMIT {int(limit)}"
        rows = await self.conn.execute_fetchall(query, params)
        return [self._row_to_meme(r) for r in rows]

    # ── Tags (continued) ──────────────────────────────────────

    async def add_tag(self, meme_id: int, tag_name: str) -> None:
        """Add a tag to a meme, creating the tag if needed."""
        await self.conn.execute(
            "INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,)
        )
        row = await self.conn.execute_fetchall("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_id = row[0]["id"]
        await self.conn.execute(
            "INSERT OR IGNORE INTO meme_tags (meme_id, tag_id) VALUES (?, ?)",
            (meme_id, tag_id),
        )
        await self.conn.commit()

    async def remove_tag(self, meme_id: int, tag_name: str) -> None:
        """Remove a tag from a meme."""
        await self.conn.execute(
            """DELETE FROM meme_tags WHERE meme_id = ? AND tag_id = (
                SELECT id FROM tags WHERE name = ?
            )""",
            (meme_id, tag_name),
        )
        await self.conn.commit()

    async def list_tags(self) -> list[str]:
        """List all tags."""
        rows = await self.conn.execute_fetchall("SELECT name FROM tags ORDER BY name")
        return [r["name"] for r in rows]

    # ── Fetch log (dedup) ──────────────────────────────────────

    async def is_fetched(self, source: str, source_id: str) -> bool:
        """Check if a source item has already been fetched."""
        rows = await self.conn.execute_fetchall(
            "SELECT 1 FROM fetch_log WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        return bool(rows)

    async def log_fetch(self, source: str, source_id: str) -> None:
        """Record that a source item has been fetched."""
        await self.conn.execute(
            "INSERT OR IGNORE INTO fetch_log (source, source_id) VALUES (?, ?)",
            (source, source_id),
        )
        await self.conn.commit()

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _row_to_meme(row: aiosqlite.Row) -> Meme:
        tags = json.loads(row["tags"]) if row["tags"] else []
        return Meme(
            id=row["id"],
            hash=row["hash"],
            filename=row["filename"],
            source=row["source"],
            source_id=row["source_id"],
            title=row["title"],
            url=row["url"],
            tags=tags,
            description=row["description"] if "description" in row.keys() else "",
            created_at=row["created_at"],
            post_at=row["post_at"],
        )
