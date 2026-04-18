# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Meme Downloader is a Python CLI tool for fetching, storing, and managing internet memes, with an optional QQ Bot (NoneBot2) plugin. All source code lives under `src/meme_downloader/`.

## Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Install with bot support
pip install -e ".[bot]"

# Run tests (asyncio_mode = "auto")
pytest

# Run a single test
pytest tests/test_foo.py::test_name -v

# Lint (ruff, line-length=100, target py310)
ruff check src/

# CLI entry point
meme --help
meme sync --source reddit --limit 50
meme search "keyword"
```

## Architecture

The codebase is fully async (aiosqlite + httpx) with four modules:

- **cli/** — Click-based CLI. `main.py` defines all commands; `utils.py` provides `db_session()` (async context manager for DB) and `get_http_client()`. Sync Click commands delegate to async implementations via `run_async()`.

- **fetchers/** — Pluggable data source architecture. `BaseFetcher` (ABC in `base.py`) defines `fetch()` → `list[FetchResult]` and `save()` (downloads image, SHA256 dedup, writes to disk + DB). `registry.py` maps source name strings to fetcher classes via `get_fetcher()`. Implemented: `RedditFetcher` (public JSON API, no auth), `ImgurFetcher` (requires `client_id` config).

- **db/** — `Database` class wrapping aiosqlite. Single `metadata.db` SQLite file with tables: `memes`, `tags`, `meme_tags`, `fetch_log`. The `Meme` dataclass is the core domain object.

- **bot/** — NoneBot2 plugin using OneBot v11 adapter. `bot.py` is the entry point; `plugin.py` registers command handlers. The bot shares the same DB and storage layer as the CLI via `db_session()`.

**Data flow:** CLI/Bot → Fetcher.fetch() → FetchResult list → BaseFetcher.save() (download + hash check + write file + insert DB row + log fetch source_id).

## Key Conventions

- Python 3.10+ with `from __future__ import annotations` in all modules
- Build system: hatchling, package layout uses `src/` directory
- Config loaded from `~/.meme-downloader/config.yaml`; `Config.load()` returns defaults if file doesn't exist
- Image files stored at `~/.meme-downloader/memes/` with filename = `{sha256_hash}{ext}`
- Deduplication: SHA256 hash on image content + `fetch_log` table tracking `(source, source_id)` pairs
- CLI output uses `rich` for tables and colored console output
