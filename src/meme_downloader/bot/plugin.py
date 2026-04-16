"""Meme Downloader NoneBot2 plugin.

Provides QQ group commands for searching and sending memes.

User commands:
    /来张梗图 [关键词]        - Random meme (optionally filtered by keyword)
    /梗图搜索 <关键词>        - Search memes
    /今日热图                 - Today's popular memes
    /梗图标签                 - List all tags
    /标签 <标签名>            - Random meme by tag
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageEvent
from nonebot.params import CommandArg

from meme_downloader.config import Config
from meme_downloader.db.database import Database
from meme_downloader.cli.utils import db_session

# ── Helpers ──────────────────────────────────────────────────

_plugin_config = Config.load()


async def _get_memes_dir() -> Path:
    config = Config.load()
    config.ensure_dirs()
    return config.memes_dir


async def _send_meme_image(bot: Bot, event: MessageEvent, meme) -> None:
    """Send a meme image to the chat."""
    config = Config.load()
    filepath = config.memes_dir / meme.filename
    if not filepath.exists():
        await bot.send(event, Message(f"[图片文件不存在: {meme.filename}]"))
        return

    # Send as CQ image
    message = Message(f"[CQ:image,file=file:///{filepath}]")
    await bot.send(event, message)


async def _get_meme_info_text(meme, index: int | None = None) -> str:
    prefix = f"{index}. " if index is not None else ""
    tags = ", ".join(meme.tags) if meme.tags else "-"
    return f"{prefix}{meme.title or '(untitled)'}\n  来源: {meme.source} | 标签: {tags} | ID: {meme.id}"


# ── Command: /来张梗图 ───────────────────────────────────────

meme_random = on_command("来张梗图", aliases={"随机梗图"}, priority=10, block=True)


@meme_random.handle()
async def handle_random(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    keyword = args.extract_plain_text().strip()
    async with db_session() as db:
        if keyword:
            memes = await db.search_memes(keyword=keyword, limit=5)
            if not memes:
                await meme_random.finish(f"没有找到关于「{keyword}」的梗图 >_<")
            import random
            meme = random.choice(memes)
        else:
            memes = await db.random_memes(count=1)
            if not memes:
                await meme_random.finish("还没有收藏任何梗图哦，先用 meme sync 抓取一些吧~")
            meme = memes[0]

    await _send_meme_image(bot, event, meme)


# ── Command: /梗图搜索 ───────────────────────────────────────

meme_search = on_command("梗图搜索", aliases={"搜索梗图"}, priority=10, block=True)


@meme_search.handle()
async def handle_search(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    keyword = args.extract_plain_text().strip()
    if not keyword:
        await meme_search.finish("请输入搜索关键词，例如: /梗图搜索 猫")

    async with db_session() as db:
        memes = await db.search_memes(keyword=keyword, limit=10)

    if not memes:
        await meme_search.finish(f"没有找到关于「{keyword}」的梗图")

    lines = [f"搜索「{keyword}」的结果：\n"]
    for i, m in enumerate(memes, 1):
        lines.append(await _get_meme_info_text(m, index=i))
    lines.append("\n回复序号获取图片（暂未实现交互回复）")

    await meme_search.finish("\n".join(lines))


# ── Command: /今日热图 ───────────────────────────────────────

meme_today = on_command("今日热图", priority=10, block=True)


@meme_today.handle()
async def handle_today(bot: Bot, event: MessageEvent):
    async with db_session() as db:
        memes = await db.search_memes(limit=5)

    if not memes:
        await meme_today.finish("今日暂无热图~")

    for m in memes:
        await _send_meme_image(bot, event, m)
        await asyncio.sleep(0.3)  # Avoid rate limiting


# ── Command: /梗图标签 ───────────────────────────────────────

meme_tags = on_command("梗图标签", priority=10, block=True)


@meme_tags.handle()
async def handle_tags(bot: Bot, event: MessageEvent):
    async with db_session() as db:
        tags = await db.list_tags()

    if not tags:
        await meme_tags.finish("还没有任何标签哦~")

    lines = ["已有标签：\n"]
    for t in tags:
        lines.append(f"  #{t}")

    await meme_tags.finish("\n".join(lines))


# ── Command: /标签 <tag> ────────────────────────────────────

meme_by_tag = on_command("标签", priority=10, block=True)


@meme_by_tag.handle()
async def handle_by_tag(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    tag_name = args.extract_plain_text().strip()
    if not tag_name:
        await meme_by_tag.finish("请输入标签名，例如: /标签 cats")

    async with db_session() as db:
        memes = await db.random_memes(tag=tag_name, count=1)

    if not memes:
        await meme_by_tag.finish(f"标签「{tag_name}」下没有梗图")

    await _send_meme_image(bot, event, memes[0])
