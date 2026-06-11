"""Meme Downloader CLI - main entry point and command definitions."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from meme_downloader.config import Config
from meme_downloader.cli.utils import db_session, get_http_client, is_vector_enabled

console = Console()


def run_async(coro):
    """Helper to run an async function from sync Click commands."""
    return asyncio.run(coro)


# ── Main group ──────────────────────────────────────────────

@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Meme Downloader - fetch and manage internet memes."""


# ── sync ────────────────────────────────────────────────────

@cli.command()
@click.option("--source", "-s", default=None, help="Only fetch from this source (e.g. reddit, imgur)")
@click.option("--limit", "-n", default=20, help="Max items to fetch per source")
@click.option("--tag", "-t", default=None, help="Auto-tag fetched items")
@click.option("--keyword", "-k", default=None, help="Search keyword (gengtu source)")
def sync(source: str | None, limit: int, tag: str | None, keyword: str | None):
    """Fetch new memes from configured sources."""
    run_async(_sync(source, limit, tag, keyword))


async def _sync(source: str | None, limit: int, tag: str | None, keyword: str | None):
    from meme_downloader.fetchers.registry import get_fetcher, list_sources

    config = Config.load()
    config.ensure_dirs()

    vector_ready = is_vector_enabled(config)
    embedding_client = None
    store = None
    if vector_ready:
        try:
            from meme_downloader.vector.embedding import EmbeddingClient
            from meme_downloader.vector.store import MilvusStore
            import asyncio

            embedding_client = EmbeddingClient(config.vector.embedding)
            store = MilvusStore(config.vector.milvus, dimensions=config.vector.embedding.dimensions)
            await asyncio.to_thread(store.connect)
        except Exception as e:
            console.print(f"[yellow]Vector store unavailable, skipping embeddings: {e}[/yellow]")
            vector_ready = False

    async with db_session(config) as db:
        async with get_http_client() as client:
            sources = [source] if source else list_sources()
            total_saved = 0

            for src_name in sources:
                try:
                    fetcher = get_fetcher(src_name, db, config.memes_dir, client)
                except ValueError as e:
                    console.print(f"[red]{e}[/red]")
                    continue

                console.print(f"[bold blue]Fetching from {src_name}...[/bold blue]")
                results = await fetcher.fetch(limit=limit, keyword=keyword or "")

                saved = 0
                for result in results:
                    meme = await fetcher.save(result)
                    if meme:
                        if tag:
                            await db.add_tag(meme.id, tag)
                        saved += 1
                        console.print(f"  [green]+[/green] {meme.title[:60]}")

                        if vector_ready and embedding_client and store and meme.description:
                            try:
                                import asyncio
                                embedding = await embedding_client.embed_text(meme.description)
                                if embedding:
                                    await asyncio.to_thread(store.upsert, meme.id, meme.source, embedding)
                            except Exception:
                                pass

                console.print(f"  [dim]{saved}/{len(results)} saved from {src_name}[/dim]")
                total_saved += saved

    if store:
        try:
            import asyncio
            await asyncio.to_thread(store.disconnect)
        except Exception:
            pass

    console.print(f"\n[bold green]Done. {total_saved} new memes saved.[/bold green]")


# ── search ──────────────────────────────────────────────────

@cli.command()
@click.argument("keyword")
@click.option("--source", "-s", default=None, help="Filter by source")
@click.option("--tag", "-t", default=None, help="Filter by tag")
@click.option("--limit", "-n", default=20, help="Max results")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def search(keyword: str, source: str | None, tag: str | None, limit: int, as_json: bool):
    """Search memes by keyword."""
    run_async(_search(keyword, source, tag, limit, as_json))


async def _search(keyword: str, source: str | None, tag: str | None, limit: int, as_json: bool):
    import json as json_mod

    async with db_session() as db:
        memes = await db.search_memes(keyword=keyword, source=source or "", tag=tag or "", limit=limit)

    if not memes:
        console.print("[yellow]No results found.[/yellow]")
        return

    if as_json:
        data = [
            {"id": m.id, "hash": m.hash, "title": m.title, "source": m.source, "url": m.url}
            for m in memes
        ]
        console.print_json(json_mod.dumps(data, ensure_ascii=False, indent=2))
        return

    table = Table(title=f"Search: {keyword}")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Title", style="white", max_width=50)
    table.add_column("Source", style="green", width=10)
    table.add_column("Tags", style="yellow", max_width=20)

    for m in memes:
        table.add_row(str(m.id), m.title or "-", m.source, ", ".join(m.tags) or "-")

    console.print(table)


# ── random ──────────────────────────────────────────────────

@cli.command()
@click.option("--tag", "-t", default=None, help="Filter by tag")
@click.option("--count", "-n", default=1, help="Number of random memes")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def random(tag: str | None, count: int, as_json: bool):
    """Get random memes."""
    run_async(_random(tag, count, as_json))


async def _random(tag: str | None, count: int, as_json: bool):
    import json as json_mod

    async with db_session() as db:
        memes = await db.random_memes(tag=tag or "", count=count)

    if not memes:
        console.print("[yellow]No memes found.[/yellow]")
        return

    if as_json:
        data = [
            {"id": m.id, "hash": m.hash, "title": m.title, "source": m.source, "filename": m.filename}
            for m in memes
        ]
        console.print_json(json_mod.dumps(data, ensure_ascii=False, indent=2))
        return

    for m in memes:
        console.print(f"[cyan]#{m.id}[/cyan] {m.title or '(untitled)'} [dim][{m.source}][/dim]")
        config = Config.load()
        filepath = config.memes_dir / m.filename
        if filepath.exists():
            console.print(f"  [dim]{filepath}[/dim]")


# ── info ────────────────────────────────────────────────────

@cli.command()
@click.argument("query")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def info(query: str, as_json: bool):
    """Show details for a meme by ID or hash."""
    run_async(_info(query, as_json))


async def _info(query: str, as_json: bool):
    import json as json_mod

    async with db_session() as db:
        meme = None
        if query.isdigit():
            meme = await db.get_meme_by_id(int(query))
        if meme is None:
            meme = await db.get_meme_by_hash(query)

    if meme is None:
        console.print(f"[red]Meme not found: {query}[/red]")
        return

    if as_json:
        data = {
            "id": meme.id,
            "hash": meme.hash,
            "filename": meme.filename,
            "source": meme.source,
            "source_id": meme.source_id,
            "title": meme.title,
            "url": meme.url,
            "tags": meme.tags,
            "created_at": str(meme.created_at),
            "post_at": str(meme.post_at),
        }
        console.print_json(json_mod.dumps(data, ensure_ascii=False, indent=2))
        return

    console.print(f"[bold]{meme.title or '(untitled)'}[/bold]")
    console.print(f"  ID:     {meme.id}")
    console.print(f"  Hash:   {meme.hash}")
    console.print(f"  Source: {meme.source} ({meme.source_id})")
    console.print(f"  URL:    {meme.url}")
    console.print(f"  Tags:   {', '.join(meme.tags) or '-'}")
    console.print(f"  Added:  {meme.created_at}")
    console.print(f"  Posted: {meme.post_at}")

    config = Config.load()
    filepath = config.memes_dir / meme.filename
    if filepath.exists():
        console.print(f"  File:   {filepath}")


# ── sources ─────────────────────────────────────────────────

@cli.command("sources")
def list_sources_cmd():
    """List available data sources."""
    from meme_downloader.fetchers.registry import list_sources

    sources = list_sources()
    table = Table(title="Available Sources")
    table.add_column("Source", style="cyan")
    for s in sources:
        table.add_row(s)
    console.print(table)


# ── export ──────────────────────────────────────────────────

@cli.command("export")
@click.argument("query")
@click.option("--dest", "-d", default=".", help="Destination directory")
def export_cmd(query: str, dest: str):
    """Export a meme file by ID or hash to a directory."""
    run_async(_export(query, dest))


async def _export(query: str, dest: str):
    config = Config.load()

    async with db_session(config) as db:
        meme = None
        if query.isdigit():
            meme = await db.get_meme_by_id(int(query))
        if meme is None:
            meme = await db.get_meme_by_hash(query)

    if meme is None:
        console.print(f"[red]Meme not found: {query}[/red]")
        return

    src = config.memes_dir / meme.filename
    if not src.exists():
        console.print(f"[red]File not found: {src}[/red]")
        return

    dest_dir = Path(dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / f"{meme.title or meme.hash}{Path(meme.filename).suffix}"
    shutil.copy2(src, dest_file)
    console.print(f"[green]Exported to {dest_file}[/green]")


# ── tag ─────────────────────────────────────────────────────

@cli.group()
def tag():
    """Manage tags on memes."""


@tag.command("add")
@click.argument("meme_id", type=int)
@click.argument("tag_name")
def tag_add(meme_id: int, tag_name: str):
    """Add a tag to a meme."""
    run_async(_tag_add(meme_id, tag_name))


async def _tag_add(meme_id: int, tag_name: str):
    async with db_session() as db:
        meme = await db.get_meme_by_id(meme_id)
        if meme is None:
            console.print(f"[red]Meme not found: {meme_id}[/red]")
            return
        await db.add_tag(meme_id, tag_name)
    console.print(f"[green]Tagged #{meme_id} with '{tag_name}'[/green]")


@tag.command("remove")
@click.argument("meme_id", type=int)
@click.argument("tag_name")
def tag_remove(meme_id: int, tag_name: str):
    """Remove a tag from a meme."""
    run_async(_tag_remove(meme_id, tag_name))


async def _tag_remove(meme_id: int, tag_name: str):
    async with db_session() as db:
        await db.remove_tag(meme_id, tag_name)
    console.print(f"[green]Removed '{tag_name}' from #{meme_id}[/green]")


@tag.command("list")
def tag_list():
    """List all tags."""
    run_async(_tag_list())


async def _tag_list():
    async with db_session() as db:
        tags = await db.list_tags()
    if not tags:
        console.print("[yellow]No tags yet.[/yellow]")
        return
    for t in tags:
        console.print(f"  {t}")


# ── stats ───────────────────────────────────────────────────

@cli.command()
def stats():
    """Show collection statistics."""
    run_async(_stats())


async def _stats():
    async with db_session() as db:
        s = await db.get_stats()

    console.print(f"[bold]Total memes:[/bold] {s['total_memes']}")
    console.print(f"[bold]Total tags:[/bold]  {s['total_tags']}")

    if s["by_source"]:
        table = Table(title="By Source")
        table.add_column("Source", style="cyan")
        table.add_column("Count", style="green", justify="right")
        for source, count in s["by_source"].items():
            table.add_row(source, str(count))
        console.print(table)


# ── similar ─────────────────────────────────────────────────

@cli.command()
@click.argument("query")
@click.option("--source", "-s", default=None, help="Filter by source")
@click.option("--limit", "-n", default=10, help="Max results")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def similar(query: str, source: str | None, limit: int, as_json: bool):
    """Find memes similar to a text description."""
    run_async(_similar(query, source, limit, as_json))


async def _similar(query: str, source: str | None, limit: int, as_json: bool):
    config = Config.load()
    if not is_vector_enabled(config):
        console.print("[yellow]Vector search is not configured.[/yellow]")
        console.print("Add vector config to ~/.meme-downloader/config.yaml:")
        console.print("  vector:")
        console.print("    enabled: true")
        console.print("    embedding:")
        console.print("      api_key: your-dashscope-api-key")
        console.print("    milvus:")
        console.print("      uri: http://localhost:19530")
        return

    try:
        from meme_downloader.vector.embedding import EmbeddingClient
        from meme_downloader.vector.store import MilvusStore
    except ImportError:
        console.print("[yellow]Install vector support: pip install meme-downloader[vector][/yellow]")
        return

    import asyncio

    embedding_client = EmbeddingClient(config.vector.embedding)
    query_embedding = await embedding_client.embed_text(query)
    if query_embedding is None:
        console.print("[red]Failed to generate embedding for query.[/red]")
        return

    store = MilvusStore(config.vector.milvus, dimensions=config.vector.embedding.dimensions)
    try:
        await asyncio.to_thread(store.connect)
        results = await asyncio.to_thread(store.search, query_embedding, top_k=limit, source=source or "")
    finally:
        await asyncio.to_thread(store.disconnect)

    if not results:
        console.print("[yellow]No similar memes found.[/yellow]")
        return

    async with db_session(config) as db:
        memes = []
        for r in results:
            meme = await db.get_meme_by_id(r.meme_id)
            if meme:
                memes.append((meme, r.score))

    if as_json:
        import json as json_mod
        data = [
            {"id": m.id, "title": m.title, "source": m.source, "score": round(s, 4), "description": m.description}
            for m, s in memes
        ]
        console.print_json(json_mod.dumps(data, ensure_ascii=False, indent=2))
        return

    table = Table(title=f"Similar to: {query}")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Score", style="magenta", width=8)
    table.add_column("Title", style="white", max_width=40)
    table.add_column("Source", style="green", width=10)
    table.add_column("Description", style="dim", max_width=30)

    for meme, score in memes:
        table.add_row(
            str(meme.id),
            f"{score:.3f}",
            meme.title or "-",
            meme.source,
            (meme.description or "-")[:30],
        )

    console.print(table)


# ── index ────────────────────────────────────────────────────

@cli.command()
@click.option("--source", "-s", default=None, help="Only index memes from this source")
@click.option("--limit", "-n", default=100, help="Max memes to index")
def index(source: str | None, limit: int):
    """Index existing memes into the vector store for similarity search."""
    run_async(_index(source, limit))


async def _index(source: str | None, limit: int):
    config = Config.load()
    if not is_vector_enabled(config):
        console.print("[yellow]Vector search is not configured.[/yellow]")
        return

    try:
        from meme_downloader.vector.embedding import EmbeddingClient
        from meme_downloader.vector.store import MilvusStore
    except ImportError:
        console.print("[yellow]Install vector support: pip install meme-downloader[vector][/yellow]")
        return

    import asyncio

    embedding_client = EmbeddingClient(config.vector.embedding)
    store = MilvusStore(config.vector.milvus, dimensions=config.vector.embedding.dimensions)

    async with db_session(config) as db:
        memes = await db.get_memes_with_descriptions(source=source or "", limit=limit)

    if not memes:
        console.print("[yellow]No memes with descriptions to index.[/yellow]")
        return

    console.print(f"[bold]Indexing {len(memes)} memes...[/bold]")

    texts = [m.description for m in memes]
    embeddings = await embedding_client.embed_batch(texts)

    meme_ids = [m.id for m in memes]
    sources = [m.source for m in memes]
    valid_embeddings = [e for e in embeddings if e is not None]
    valid_ids = [mid for mid, e in zip(meme_ids, embeddings) if e is not None]
    valid_sources = [s for s, e in zip(sources, embeddings) if e is not None]

    if not valid_embeddings:
        console.print("[red]Failed to generate any embeddings.[/red]")
        return

    try:
        await asyncio.to_thread(store.connect)
        await asyncio.to_thread(store.upsert_batch, valid_ids, valid_sources, valid_embeddings)
        console.print(f"[bold green]Indexed {len(valid_embeddings)}/{len(memes)} memes.[/bold green]")
    finally:
        await asyncio.to_thread(store.disconnect)
