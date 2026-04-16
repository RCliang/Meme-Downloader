# Meme Downloader Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个获取网络热门梗图和表情包的 CLI 工具，带 QQ Bot 插件支持

**Architecture:** Python CLI 工具 + SQLite 元数据存储 + NoneBot2 QQ Bot 插件，数据通过共享数据库交互

**Tech Stack:** Python 3.10+, Click/CLI 框架, SQLite, aiohttp, NoneBot2, NapCat/LLOneBot

---

## 阶段 1: 项目初始化

### Task 1.1: 创建项目结构和 pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/meme_downloader/__init__.py`

**Step 1: 创建 pyproject.toml**

```toml
[project]
name = "meme-downloader"
version = "0.1.0"
description = "A tool to fetch and manage popular memes from the internet"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "click>=8.1.0",
    "httpx>=0.25.0",
    "aiohttp>=3.9.0",
    "feedparser>=6.0.10",
    "sqlalchemy>=2.0.23",
    "pydantic>=2.5.0",
    "python-dotenv>=1.0.0",
    "rich>=13.7.0",
]

[project.optional-dependencies]
bot = [
    "nonebot2[fastapi]>=2.2.0",
    "nonebot-adapter-onebot>=2.3.0",
]

[project.scripts]
meme = "meme_downloader.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

**Step 2: 创建 README.md**

```markdown
# Meme Downloader

获取网络热门梗图和表情包的 CLI 工具。

## 安装

```bash
pip install -e .
```

## 使用

```bash
meme sync --source reddit --limit 50
meme search "猫咪"
meme random --tag 搞笑
```
```

**Step 3: 创建基础目录结构**

```bash
mkdir -p src/meme_downloader/{core,fetchers,cli,bot}
mkdir -p tests/{unit,integration}
touch src/meme_downloader/__init__.py
touch src/meme_downloader/core/__init__.py
touch src/meme_downloader/fetchers/__init__.py
touch src/meme_downloader/cli/__init__.py
touch src/meme_downloader/bot/__init__.py
touch tests/__init__.py
```

**Step 4: 提交**

```bash
git add pyproject.toml README.md src/ tests/
git commit -m "feat: initialize project structure and dependencies"
```

---

### Task 1.2: 配置管理系统

**Files:**
- Create: `src/meme_downloader/core/config.py`
- Create: `src/meme_downloader/core/constants.py`
- Create: `meme_downloader.example.yaml`

**Step 1: 创建配置文件示例**

```yaml
# meme_downloader.example.yaml
storage:
  home_dir: "~/.meme-downloader"
  memes_dir: "memes"
  database: "metadata.db"

sources:
  reddit:
    enabled: true
    subreddits: ["memes", "dankmemes", "wholesomememes"]
    limit: 50

  weibo:
    enabled: false
    # 需要配置 API 密钥

  bilibili:
    enabled: true
    limit: 30

bot:
  enabled: false
  command_prefix: "/"
  whitelist:
    groups: []
    users: []
```

**Step 2: 编写配置管理代码**

```python
# src/meme_downloader/core/config.py
from pathlib import Path
from typing import Any
import yaml
import click

class Config:
    def __init__(self, config_path: Path | None = None):
        self.home_dir = Path.home() / ".meme-downloader"
        self.config_path = config_path or (self.home_dir / "config.yaml")
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._default_config()

    def _default_config(self) -> dict[str, Any]:
        return {
            "storage": {
                "home_dir": str(self.home_dir),
                "memes_dir": "memes",
                "database": "metadata.db",
            },
            "sources": {
                "reddit": {"enabled": True, "limit": 50},
                "bilibili": {"enabled": True, "limit": 30},
            },
            "bot": {"enabled": False, "command_prefix": "/"},
        }

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def ensure_directories(self) -> None:
        self.home_dir.mkdir(parents=True, exist_ok=True)
        (self.home_dir / self._config["storage"]["memes_dir"]).mkdir(parents=True, exist_ok=True)
        (self.home_dir / "logs").mkdir(parents=True, exist_ok=True)

def get_config() -> Config:
    return Config()
```

**Step 3: 编写测试**

```python
# tests/unit/test_config.py
import pytest
from pathlib import Path
from meme_downloader.core.config import Config

def test_config_default_values():
    config = Config()
    assert config.get("storage.home_dir") == str(Path.home() / ".meme-downloader")
    assert config.get("storage.database") == "metadata.db"

def test_config_get_with_default():
    config = Config()
    assert config.get("nonexistent.key", "default") == "default"
```

**Step 4: 运行测试验证**

```bash
cd /e/personal/new_proj/Meme-Downloader/.worktrees/impl
pip install -e pyyaml
pytest tests/unit/test_config.py -v
```

**Step 5: 提交**

```bash
git add src/meme_downloader/core/config.py tests/unit/test_config.py meme_downloader.example.yaml
git commit -m "feat: add configuration management system"
```

---

## 阶段 2: 数据模型和存储

### Task 2.1: 数据库模型定义

**Files:**
- Create: `src/meme_downloader/core/models.py`
- Create: `src/meme_downloader/core/database.py`

**Step 1: 编写数据模型**

```python
# src/meme_downloader/core/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import list

@dataclass
class Meme:
    id: int | None = None
    hash: str = ""
    filename: str = ""
    source: str = ""
    source_id: str = ""
    title: str = ""
    url: str = ""
    tags: list[str] | None = None
    created_at: datetime | None = None
    post_at: datetime | None = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now()
```

**Step 2: 编写数据库操作层**

```python
# src/meme_downloader/core/database.py
from pathlib import Path
from sqlite3 import Connection, Row, connect
from typing import Optional
from contextlib import contextmanager

from meme_downloader.core.config import Config
from meme_downloader.core.models import Meme

class Database:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        db_path = self.config.home_dir / self.config.get("storage.database", "metadata.db")
        self.db_path = db_path
        self._ensure_schema()

    @contextmanager
    def _get_conn(self) -> Connection:
        conn = connect(str(self.db_path))
        conn.row_factory = Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    title TEXT,
                    url TEXT NOT NULL,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    post_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meme_tags (
                    meme_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (meme_id, tag_id),
                    FOREIGN KEY (meme_id) REFERENCES memes(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                )
            """)
            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memes_hash ON memes(hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memes_source ON memes(source)")

    def add_meme(self, meme: Meme) -> int:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO memes (hash, filename, source, source_id, title, url, tags, post_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (meme.hash, meme.filename, meme.source, meme.source_id,
                 meme.title, meme.url, str(meme.tags), meme.post_at),
            )
            return cursor.lastrowid

    def get_by_hash(self, hash: str) -> Optional[Meme]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM memes WHERE hash = ?", (hash,)).fetchone()
            if row:
                return self._row_to_meme(row)
            return None

    def exists(self, hash: str) -> bool:
        return self.get_by_hash(hash) is not None

    def search(self, query: str = "", source: str = "", tag: str = "", limit: int = 20) -> list[Meme]:
        with self._get_conn() as conn:
            sql = "SELECT * FROM memes WHERE 1=1"
            params = []

            if query:
                sql += " AND title LIKE ?"
                params.append(f"%{query}%")
            if source:
                sql += " AND source = ?"
                params.append(source)
            if tag:
                sql += " AND tags LIKE ?"
                params.append(f"%{tag}%")

            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_meme(row) for row in rows]

    def get_random(self, tag: str = "", count: int = 1) -> list[Meme]:
        with self._get_conn() as conn:
            if tag:
                rows = conn.execute(
                    "SELECT * FROM memes WHERE tags LIKE ? ORDER BY RANDOM() LIMIT ?",
                    (f"%{tag}%", count)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memes ORDER BY RANDOM() LIMIT ?",
                    (count,)
                ).fetchall()
            return [self._row_to_meme(row) for row in rows]

    def _row_to_meme(self, row: Row) -> Meme:
        import ast
        tags = ast.literal_eval(row["tags"]) if row["tags"] else []
        return Meme(
            id=row["id"],
            hash=row["hash"],
            filename=row["filename"],
            source=row["source"],
            source_id=row["source_id"],
            title=row["title"],
            url=row["url"],
            tags=tags,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            post_at=datetime.fromisoformat(row["post_at"]) if row["post_at"] else None,
        )

    def get_stats(self) -> dict:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM memes").fetchone()[0]
            by_source = conn.execute(
                "SELECT source, COUNT(*) as count FROM memes GROUP BY source"
            ).fetchall()
            return {
                "total": total,
                "by_source": {row["source"]: row["count"] for row in by_source},
            }
```

**Step 3: 编写测试**

```python
# tests/unit/test_database.py
import pytest
from pathlib import Path
import tempfile
from meme_downloader.core.database import Database
from meme_downloader.core.models import Meme
from datetime import datetime

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        # 使用临时数据库
        import os
        os.environ["MEME_TEST_DB"] = str(db_path)
        yield db_path

def test_database_create_schema(temp_db):
    # 确保表被创建
    assert temp_db.exists()

def test_add_and_retrieve_meme(temp_db):
    db = Database.__new__(Database)  # 跳过 __init__ 中的默认路径
    db.db_path = temp_db
    db._ensure_schema()

    meme = Meme(
        hash="abc123",
        filename="abc123.jpg",
        source="test",
        url="https://example.com/img.jpg",
        title="测试梗图"
    )
    meme_id = db.add_meme(meme)
    assert meme_id > 0

    retrieved = db.get_by_hash("abc123")
    assert retrieved is not None
    assert retrieved.hash == "abc123"
    assert retrieved.title == "测试梗图"

def test_duplicate_detection(temp_db):
    db = Database.__new__(Database)
    db.db_path = temp_db
    db._ensure_schema()

    meme = Meme(
        hash="dup123",
        filename="dup123.jpg",
        source="test",
        url="https://example.com/dup.jpg"
    )
    db.add_meme(meme)

    assert db.exists("dup123") is True
    assert db.exists("nonexistent") is False
```

**Step 4: 运行测试**

```bash
cd /e/personal/new_proj/Meme-Downloader/.worktrees/impl
pip install -e .
pytest tests/unit/test_database.py -v
```

**Step 5: 提交**

```bash
git add src/meme_downloader/core/models.py src/meme_downloader/core/database.py tests/unit/test_database.py
git commit -m "feat: add database models and operations"
```

---

### Task 2.2: 图片下载和去重

**Files:**
- Create: `src/meme_downloader/core/downloader.py`
- Create: `src/meme_downloader/core/utils.py`

**Step 1: 编写工具函数**

```python
# src/meme_downloader/core/utils.py
import hashlib
from pathlib import Path
from typing import BinaryIO

def calculate_hash(file: BinaryIO | bytes) -> str:
    """计算文件的 SHA256 哈希"""
    sha256 = hashlib.sha256()
    if isinstance(file, bytes):
        sha256.update(file)
    else:
        for chunk in iter(lambda: file.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def sanitize_filename(name: str) -> str:
    """清理文件名，移除非法字符"""
    import re
    # 移除或替换非法字符
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', name)
    # 限制长度
    return cleaned[:200]
```

**Step 2: 编写下载器**

```python
# src/meme_downloader/core/downloader.py
from pathlib import Path
import httpx
from typing import Optional

from meme_downloader.core.config import Config
from meme_downloader.core.utils import calculate_hash

class Downloader:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.memes_dir = self.config.home_dir / self.config.get("storage.memes_dir", "memes")
        self.memes_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)

    def download(self, url: str) -> tuple[bytes, str]:
        """下载图片并返回 (内容, hash)"""
        response = self.client.get(url)
        response.raise_for_status()
        content = response.content
        hash = calculate_hash(content)
        return content, hash

    def save(self, content: bytes, hash: str, extension: str = "jpg") -> Path:
        """保存图片到本地"""
        filename = f"{hash}.{extension}"
        path = self.memes_dir / filename
        if not path.exists():
            path.write_bytes(content)
        return path

    def download_and_save(self, url: str) -> tuple[Path, str]:
        """下载并保存，返回 (路径, hash)"""
        content, hash = self.download(url)
        # 从 URL 或内容类型推断扩展名
        extension = self._get_extension(url, content)
        path = self.save(content, hash, extension)
        return path, hash

    def _get_extension(self, url: str, content: bytes) -> str:
        """推断文件扩展名"""
        # 从 URL 获取
        if "." in url.split("?")[0]:
            ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
            if ext in {"jpg", "jpeg", "png", "gif", "webp", "bmp"}:
                return ext

        # 从内容类型获取
        import imghdr
        img_type = imghdr.what(None, h=content)
        if img_type:
            return img_type if img_type != "jpeg" else "jpg"

        return "jpg"  # 默认

    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()
```

**Step 3: 编写测试**

```python
# tests/unit/test_downloader.py
import pytest
from pathlib import Path
import tempfile
from meme_downloader.core.downloader import Downloader
from meme_downloader.core.utils import calculate_hash

def test_calculate_hash():
    data = b"test data"
    hash = calculate_hash(data)
    assert len(hash) == 64  # SHA256 长度
    assert isinstance(hash, str)

def test_downloader_save(temp_path: Path):
    downloader = Downloader.__new__(Downloader)
    downloader.memes_dir = temp_path

    content = b"fake image content"
    hash = calculate_hash(content)
    path = downloader.save(content, hash, "jpg")

    assert path.exists()
    assert path.name == f"{hash}.jpg"
    assert path.read_bytes() == content
```

**Step 4: 运行测试**

```bash
cd /e/personal/new_proj/Meme-Downloader/.worktrees/impl
pytest tests/unit/test_downloader.py -v
```

**Step 5: 提交**

```bash
git add src/meme_downloader/core/downloader.py src/meme_downloader/core/utils.py tests/unit/test_downloader.py
git commit -m "feat: add image downloader with deduplication"
```

---

## 阶段 3: Fetcher 采集器框架

### Task 3.1: 基础 Fetcher 抽象类

**Files:**
- Create: `src/meme_downloader/fetchers/base.py`

**Step 1: 编写基础抽象类**

```python
# src/meme_downloader/fetchers/base.py
from abc import ABC, abstractmethod
from typing import list
from meme_downloader.core.models import Meme

class BaseFetcher(ABC):
    """所有采集器的基类"""

    source_name: str = ""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)

    @abstractmethod
    async def fetch(self, limit: int = 50) -> list[Meme]:
        """抓取指定数量的梗图"""
        pass

    @abstractmethod
    def parse_meme(self, raw_data: dict) -> Meme:
        """将原始数据转换为 Meme 对象"""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(enabled={self.enabled})"
```

**Step 2: 提交**

```bash
git add src/meme_downloader/fetchers/base.py
git commit -m "feat: add base fetcher abstract class"
```

---

### Task 3.2: Reddit Fetcher

**Files:**
- Create: `src/meme_downloader/fetchers/reddit.py`

**Step 1: 编写 Reddit Fetcher**

```python
# src/meme_downloader/fetchers/reddit.py
import aiohttp
from typing import list
from datetime import datetime

from meme_downloader.fetchers.base import BaseFetcher
from meme_downloader.core.models import Meme

class RedditFetcher(BaseFetcher):
    """从 Reddit 子版块抓取热门梗图"""

    source_name = "reddit"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.subreddits = self.config.get("subreddits", ["memes", "dankmemes"])
        self.base_url = "https://www.reddit.com/r/{}/hot.json?limit=50"

    async def fetch(self, limit: int = 50) -> list[Meme]:
        memes = []

        async with aiohttp.ClientSession() as session:
            for subreddit in self.subreddits:
                if len(memes) >= limit:
                    break

                url = self.base_url.format(subreddit)
                try:
                    async with session.get(url, headers={"User-Agent": "MemeDownloader/1.0"}) as resp:
                        resp.raise_for_status()
                        data = await resp.json()

                        for post in data["data"]["children"]:
                            if len(memes) >= limit:
                                break
                            meme = self._parse_post(post["data"], subreddit)
                            if meme:
                                memes.append(meme)

                except Exception as e:
                    print(f"Error fetching from r/{subreddit}: {e}")
                    continue

        return memes

    def _parse_post(self, post: dict, subreddit: str) -> Meme | None:
        """解析 Reddit 帖子数据"""
        url = post.get("url_overridden_by_dest") or post.get("url")
        if not url:
            return None

        # 只获取图片 URL
        if not any(url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
            return None

        return Meme(
            source="reddit",
            source_id=post["id"],
            title=post.get("title", ""),
            url=url,
            post_at=datetime.fromtimestamp(post.get("created_utc", 0)),
            tags=["reddit", subreddit]
        )
```

**Step 2: 编写测试**

```python
# tests/unit/test_reddit_fetcher.py
import pytest
from meme_downloader.fetchers.reddit import RedditFetcher

@pytest.mark.asyncio
async def test_reddit_fetcher_init():
    fetcher = RedditFetcher({"subreddits": ["test"]})
    assert fetcher.source_name == "reddit"
    assert fetcher.subreddits == ["test"]
    assert fetcher.enabled is True

def test_parse_post():
    fetcher = RedditFetcher()
    post_data = {
        "id": "abc123",
        "title": "Test meme",
        "url": "https://example.com/meme.jpg",
        "url_overridden_by_dest": "https://i.redd.it/abc123.jpg",
        "created_utc": 1609459200,
    }
    meme = fetcher._parse_post(post_data, "memes")
    assert meme is not None
    assert meme.source == "reddit"
    assert meme.source_id == "abc123"
    assert "memes" in meme.tags
```

**Step 3: 运行测试**

```bash
cd /e/personal/new_proj/Meme-Downloader/.worktrees/impl
pytest tests/unit/test_reddit_fetcher.py -v
```

**Step 4: 提交**

```bash
git add src/meme_downloader/fetchers/reddit.py tests/unit/test_reddit_fetcher.py
git commit -m "feat: add Reddit fetcher"
```

---

### Task 3.3: RSS Fetcher (通用)

**Files:**
- Create: `src/meme_downloader/fetchers/rss.py`

**Step 1: 编写 RSS Fetcher**

```python
# src/meme_downloader/fetchers/rss.py
import feedparser
from typing import list
from datetime import datetime

from meme_downloader.fetchers.base import BaseFetcher
from meme_downloader.core.models import Meme

class RSSFetcher(BaseFetcher):
    """通用 RSS 订阅采集器"""

    source_name = "rss"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.feeds = self.config.get("feeds", [])
        self.source_label = self.config.get("source", "rss")

    async def fetch(self, limit: int = 50) -> list[Meme]:
        memes = []

        for feed_url in self.feeds:
            if len(memes) >= limit:
                break

            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:limit]:
                    if len(memes) >= limit:
                        break
                    meme = self._parse_entry(entry)
                    if meme:
                        memes.append(meme)
            except Exception as e:
                print(f"Error fetching RSS from {feed_url}: {e}")
                continue

        return memes

    def _parse_entry(self, entry: dict) -> Meme | None:
        """解析 RSS 条目"""
        # 尝试获取图片链接
        url = self._extract_image_url(entry)
        if not url:
            return None

        return Meme(
            source=self.source_label,
            source_id=entry.get("id", entry.get("link", "")),
            title=entry.get("title", ""),
            url=url,
            tags=[self.source_label],
        )

    def _extract_image_url(self, entry: dict) -> str | None:
        """从 RSS 条目中提取图片 URL"""
        # 检查 enclosures
        if hasattr(entry, "enclosures") and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get("type", "").startswith("image/"):
                    return enc.get("href")

        # 检查 content
        if hasattr(entry, "content"):
            for content in entry.content:
                if content.get("type") == "text/html":
                    import re
                    img_match = re.search(r'<img[^>]+src="([^"]+)"', content.value)
                    if img_match:
                        return img_match.group(1)

        # 检查 media thumbnails
        if hasattr(entry, "media_content"):
            return entry.media_content[0].get("url")

        return None
```

**Step 2: 提交**

```bash
git add src/meme_downloader/fetchers/rss.py
git commit -m "feat: add generic RSS fetcher"
```

---

### Task 3.4: Fetcher 管理器

**Files:**
- Create: `src/meme_downloader/fetchers/manager.py`

**Step 1: 编写管理器**

```python
# src/meme_downloader/fetchers/manager.py
from typing import list
from meme_downloader.core.config import Config
from meme_downloader.core.models import Meme
from meme_downloader.fetchers.reddit import RedditFetcher
from meme_downloader.fetchers.rss import RSSFetcher

class FetcherManager:
    """管理所有采集器"""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.fetchers: list = []
        self._register_fetchers()

    def _register_fetchers(self) -> None:
        """注册所有启用的采集器"""
        # Reddit
        if self.config.get("sources.reddit.enabled", True):
            reddit_config = {
                "subreddits": self.config.get("sources.reddit.subreddits", ["memes"])
            }
            self.fetchers.append(RedditFetcher(reddit_config))

        # RSS feeds (可配置多个)
        rss_feeds = self.config.get("sources.rss.feeds", [])
        if rss_feeds:
            self.fetchers.append(RSSFetcher({"feeds": rss_feeds, "source": "rss"}))

    async def fetch_all(self, source: str = "", limit: int = 50) -> list[Meme]:
        """从所有采集器获取数据"""
        all_memes = []

        for fetcher in self.fetchers:
            if source and fetcher.source_name != source:
                continue
            if not fetcher.enabled:
                continue

            try:
                memes = await fetcher.fetch(limit)
                all_memes.extend(memes)
                print(f"Fetched {len(memes)} memes from {fetcher.source_name}")
            except Exception as e:
                print(f"Error in {fetcher.source_name}: {e}")

        return all_memes

    def list_sources(self) -> list[str]:
        """列出所有可用的数据源"""
        return [f.source_name for f in self.fetchers if f.enabled]
```

**Step 2: 提交**

```bash
git add src/meme_downloader/fetchers/manager.py
git commit -m "feat: add fetcher manager"
```

---

## 阶段 4: CLI 核心命令

### Task 4.1: CLI 框架搭建

**Files:**
- Create: `src/meme_downloader/cli/main.py`

**Step 1: 编写 CLI 主入口**

```python
# src/meme_downloader/cli/main.py
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from meme_downloader.core.config import Config, get_config
from meme_downloader.core.database import Database

console = Console()

@click.group()
@click.version_option(version="0.1.0")
def main():
    """Meme Downloader - 获取网络热门梗图和表情包"""
    config = get_config()
    config.ensure_directories()

@main.command()
@click.option("--source", "-s", help="指定数据源")
@click.option("--limit", "-l", default=50, help="获取数量")
def sync(source: str, limit: int):
    """同步/抓取新内容"""
    console.print(f"🔄 开始同步... (source={source}, limit={limit})")
    # TODO: 实现同步逻辑
    console.print("✅ 同步完成!")

@main.command()
@click.argument("query", required=False, default="")
@click.option("--source", "-s", help="指定数据源")
@click.option("--tag", "-t", help="指定标签")
@click.option("--limit", "-l", default=20, help="结果数量")
def search(query: str, source: str, tag: str, limit: int):
    """搜索本地收藏"""
    db = Database()
    results = db.search(query, source, tag, limit)

    table = Table(title=f"搜索结果 ({len(results)} 条)")
    table.add_column("ID", style="cyan")
    table.add_column("来源", style="green")
    table.add_column("标题")
    table.add_column("标签", style="yellow")

    for meme in results:
        table.add_row(
            str(meme.id or "-"),
            meme.source,
            meme.title[:30] + "..." if len(meme.title) > 30 else meme.title,
            ",".join(meme.tags[:3]) if meme.tags else ""
        )

    console.print(table)

@main.command()
@click.option("--tag", "-t", help="指定标签")
@click.option("--count", "-c", default=1, help="数量")
def random(tag: str, count: int):
    """随机获取梗图"""
    db = Database()
    memes = db.get_random(tag, count)

    for meme in memes:
        console.print(f"🎲 {meme.title}")
        console.print(f"   来源: {meme.source} | 文件: {meme.filename}")

@main.command()
@click.argument("ident")
def info(ident: str):
    """查看详情"""
    db = Database()
    # 尝试按 ID 或 hash 查找
    if ident.isdigit():
        # TODO: 实现 get_by_id
        pass
    else:
        meme = db.get_by_hash(ident)

    if meme:
        console.print(f"[bold]标题:[/bold] {meme.title}")
        console.print(f"[bold]来源:[/bold] {meme.source}")
        console.print(f"[bold]URL:[/bold] {meme.url}")
        console.print(f"[bold]标签:[/bold] {', '.join(meme.tags)}")
    else:
        console.print("❌ 未找到")

@main.command()
def sources():
    """列出所有数据源"""
    config = get_config()
    console.print("可用的数据源:")
    for name, conf in config._config.get("sources", {}).items():
        status = "✅" if conf.get("enabled", True) else "❌"
        console.print(f"  {status} {name}")

@main.command()
def stats():
    """统计信息"""
    db = Database()
    stats = db.get_stats()

    console.print(f"[bold]总数量:[/bold] {stats['total']}")
    console.print("\n[bold]按来源:[/bold]")
    for source, count in stats['by_source'].items():
        console.print(f"  {source}: {count}")

if __name__ == "__main__":
    main()
```

**Step 2: 测试 CLI**

```bash
cd /e/personal/new_proj/Meme-Downloader/.worktrees/impl
pip install -e .
meme --help
meme sources
meme stats
```

**Step 3: 提交**

```bash
git add src/meme_downloader/cli/main.py
git commit -m "feat: add CLI framework and basic commands"
```

---

### Task 4.2: 实现同步命令

**Files:**
- Modify: `src/meme_downloader/cli/main.py`
- Create: `src/meme_downloader/cli/sync.py`

**Step 1: 编写同步逻辑**

```python
# src/meme_downloader/cli/sync.py
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from meme_downloader.core.config import Config
from meme_downloader.core.database import Database
from meme_downloader.core.downloader import Downloader
from meme_downloader.fetchers.manager import FetcherManager

async def sync(config: Config, source: str = "", limit: int = 50):
    """执行同步操作"""
    db = Database(config)
    downloader = Downloader(config)
    manager = FetcherManager(config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=config.console,
    ) as progress:
        # 获取数据
        fetch_task = progress.add_task("正在获取数据...", total=None)

        memes = await manager.fetch_all(source, limit)
        progress.update(fetch_task, completed=len(memes), total=len(memes))

        # 下载并保存
        download_task = progress.add_task("正在下载图片...", total=len(memes))

        new_count = 0
        skip_count = 0

        for meme in memes:
            progress.update(download_task, advance=1)

            # 检查是否已存在
            if meme.hash and db.exists(meme.hash):
                skip_count += 1
                continue

            try:
                # 下载图片
                path, hash = downloader.download_and_save(meme.url)
                meme.hash = hash
                meme.filename = path.name

                # 保存到数据库
                db.add_meme(meme)
                new_count += 1

            except Exception as e:
                progress.console.print(f"❌ 下载失败: {meme.url} - {e}")

    return {"new": new_count, "skip": skip_count, "total": len(memes)}
```

**Step 2: 更新 main.py**

```python
# 在 main.py 中添加
from meme_downloader.cli.sync import sync

@main.command()
@click.option("--source", "-s", help="指定数据源")
@click.option("--limit", "-l", default=50, help="获取数量")
async def _sync(source: str, limit: int):
    """同步/抓取新内容"""
    result = await sync(get_config(), source, limit)
    console.print(f"✅ 同步完成! 新增: {result['new']}, 跳过: {result['skip']}, 总计: {result['total']}")
```

**Step 3: 提交**

```bash
git add src/meme_downloader/cli/sync.py src/meme_downloader/cli/main.py
git commit -m "feat: implement sync command"
```

---

## 阶段 5: QQ Bot 插件

### Task 5.1: Bot 插件基础结构

**Files:**
- Create: `src/meme_downloader/bot/__init__.py`
- Create: `src/meme_downloader/bot/plugin.py`

**Step 1: 编写 Bot 插件**

```python
# src/meme_downloader/bot/plugin.py
from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot.plugin import PluginMetadata

from meme_downloader.core.config import Config
from meme_downloader.core.database import Database

__plugin_meta__ = PluginMetadata(
    name="Meme Downloader Bot",
    description="在 QQ 中发送梗图",
    usage="/来张梗图 [关键词] | /梗图搜索 <关键词>"
)

driver = get_driver()
config: Config = driver.config

# 注册命令
meme_cmd = on_command("来张梗图", priority=5, block=True)
search_cmd = on_command("梗图搜索", priority=5, block=True)

@meme_cmd.handle()
async def handle_meme(event: MessageEvent):
    """随机发送一张梗图"""
    db = Database()

    # 获取关键词
    keyword = str(event.get_message()).strip() or None

    # 查询
    memes = db.get_random(tag=keyword or "", count=1)

    if memes:
        meme = memes[0]
        # 发送图片
        img_path = f"file://{config.home_dir / config.get('storage.memes_dir') / meme.filename}"
        await meme_cmd.finish(Message(f"[CQ:image,file={img_path}]\n来源: {meme.source}"))
    else:
        await meme_cmd.finish("没有找到相关梗图~")

@search_cmd.handle()
async def handle_search(event: MessageEvent):
    """搜索梗图"""
    db = Database()

    # 获取搜索词
    query = str(event.get_message()).strip()
    if not query:
        await search_cmd.finish("请输入搜索关键词~")

    # 搜索
    results = db.search(query=query, limit=5)

    if results:
        msg = "搜索结果:\n"
        for i, meme in enumerate(results, 1):
            msg += f"{i}. {meme.title[:20]}... ({meme.source})\n"
        await search_cmd.finish(msg)
    else:
        await search_cmd.finish("没有找到相关梗图~")
```

**Step 2: 提交**

```bash
git add src/meme_downloader/bot/plugin.py
git commit -m "feat: add QQ Bot plugin"
```

---

### Task 5.2: Bot 配置示例

**Files:**
- Create: `nonebot.example.py`
- Create: `.env.example`

**Step 1: 创建配置示例**

```python
# nonebot.example.py
from nonebot.default_config import *

HOST = "127.0.0.1"
PORT = 8080

# NapCat/LLOneBot 配置
ONEBOT_WS_URLS = ["ws://127.0.0.1:3001"]

# 加载自定义插件
custom_plugins = ["meme_downloader.bot"]
```

```bash
# .env.example
NONEBOT_PLUGIN_MEME_ENABLED=true
MEME_CONFIG_PATH=~/.meme-downloader/config.yaml
```

**Step 2: 创建 Bot 启动脚本**

```bash
# scripts/run_bot.sh
#!/bin/bash
cd "$(dirname "$0")/.."
source .venv/bin/activate
nb run
```

**Step 3: 提交**

```bash
git add nonebot.example.py .env.example scripts/
git commit -m "feat: add Bot configuration examples"
```

---

## 阶段 6: 文档和测试

### Task 6.1: 完善文档

**Files:**
- Modify: `README.md`

**Step 1: 更新 README**

```markdown
# Meme Downloader

获取网络热门梗图和表情包的 CLI 工具，支持 QQ Bot 集成。

## 功能特性

- 🔄 从多个平台自动获取热门梗图
- 🔍 本地搜索和标签管理
- 🤖 QQ Bot 集成，聊天中随时发送
- 📦 自动去重和元数据管理

## 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/meme-downloader.git
cd meme-downloader

# 安装依赖
pip install -e .

# (可选) 安装 Bot 支持
pip install -e ".[bot]"
```

## 配置

复制示例配置：

```bash
cp meme_downloader.example.yaml ~/.meme-downloader/config.yaml
```

编辑配置文件，启用需要的数据源。

## CLI 使用

```bash
# 同步最新梗图
meme sync --source reddit --limit 50

# 搜索本地收藏
meme search "猫咪"

# 随机获取
meme random --tag 搞笑

# 查看统计
meme stats
```

## QQ Bot

1. 安装 NapCat 或 LLOneBot
2. 复制 `nonebot.example.py` 为 `nonebot.py`
3. 运行 `nb run`

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest
```

## License

MIT
```

**Step 2: 提交**

```bash
git add README.md
git commit -m "docs: update README with usage instructions"
```

---

### Task 6.2: 集成测试

**Files:**
- Create: `tests/integration/test_sync.py`

**Step 1: 编写集成测试**

```python
# tests/integration/test_sync.py
import pytest
from pathlib import Path
import tempfile

from meme_downloader.core.config import Config
from meme_downloader.cli.sync import sync

@pytest.mark.asyncio
async def test_sync_integration():
    """测试完整的同步流程"""
    with tempfile.TemporaryDirectory() as tmp:
        # 使用临时目录
        config = Config()
        config.home_dir = Path(tmp)
        config.ensure_directories()

        # 运行同步
        result = await sync(config, source="reddit", limit=5)

        # 验证结果
        assert result["total"] > 0
        assert isinstance(result["new"], int)
        assert isinstance(result["skip"], int)
```

**Step 2: 提交**

```bash
git add tests/integration/test_sync.py
git commit -m "test: add integration test for sync"
```

---

## 完成清单

- [ ] 项目结构创建
- [ ] 配置管理系统
- [ ] 数据库和模型
- [ ] 图片下载器
- [ ] Fetcher 基类
- [ ] Reddit Fetcher
- [ ] RSS Fetcher
- [ ] Fetcher 管理器
- [ ] CLI 框架
- [ ] 同步命令
- [ ] 搜索命令
- [ ] 随机命令
- [ ] 统计命令
- [ ] QQ Bot 插件
- [ ] 文档完善
- [ ] 集成测试

---

## 下一步

实现完成后，可以考虑：

1. 添加更多数据源 (微博、B站、贴吧)
2. 实现标签自动识别 (使用 AI 或关键词匹配)
3. 添加图片预览功能 (在支持的终端)
4. 实现 Web UI
5. 添加导出功能 (打包分享)
