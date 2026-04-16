# Meme Downloader 设计文档

**日期**: 2026-04-15
**状态**: 设计阶段

## 概述

一个专门获取网络热门梗图和表情包的项目，包含 CLI 收藏工具和 QQ Bot 插件两个核心模块。

## 核心功能

1. 从国内外主流平台获取热门梗图和表情包
2. 本地统一存储和管理
3. 命令行搜索和导出
4. QQ Bot 集成，在聊天中发送梗图

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Meme Downloader                       │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────────┐      ┌─────────────────────┐   │
│  │   CLI 工具 (核心)    │      │  QQ Bot 插件        │   │
│  │                     │      │  (NoneBot2)         │   │
│  │  - 数据抓取         │◄────┤  - 搜索发送         │   │
│  │  - 存储管理         │      │  - 命令交互         │   │
│  │  - 命令行界面       │      │                     │   │
│  └─────────────────────┘      └─────────────────────┘   │
│            │                            ▲                │
│            ▼                            │                │
│  ┌───────────────────────────────────────────────┐     │
│  │           共享数据层                            │     │
│  │  - SQLite 元数据数据库                         │     │
│  │  - memes/ 图片存储目录                         │     │
│  └───────────────────────────────────────────────┘     │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

## 数据源和获取策略

### 原则
- RSS/API 优先，避免直接爬虫
- 每个平台独立的 Fetcher 采集器
- 统一数据格式转换

### 支持的平台

**国内**:
- 微博：热搜话题 API
- 贴吧：热门吧 RSS
- B站：动态投稿 API
- 豆瓣：热门小组 RSS

**国外**:
- Reddit：JSON API (r/memes, r/dankmemes)
- Imgur：官方 API
- Know Your Meme：RSS 订阅

### 去重策略
- SHA256 哈希去重
- 下载前检查数据库
- 重复图片只记录来源引用

## 数据模型和存储

### 目录结构
```
~/.meme-downloader/
├── memes/              # 图片文件，文件名 = SHA256.hex
├── metadata.db         # SQLite 数据库
├── config.yaml         # 配置文件
└── logs/               # 日志
```

### 数据库表结构

**memes 表**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| hash | TEXT | SHA256，唯一索引 |
| filename | TEXT | 本地文件名 |
| source | TEXT | 来源平台 |
| source_id | TEXT | 原平台 ID |
| title | TEXT | 标题/描述 |
| url | TEXT | 原始 URL |
| tags | TEXT | JSON 数组 |
| created_at | TIMESTAMP | 抓取时间 |
| post_at | TIMESTAMP | 发布时间 |

**tags 表**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | TEXT | 标签名，唯一 |

**meme_tags 关联表**
| 字段 | 类型 | 说明 |
|------|------|------|
| meme_id | INTEGER | 外键 |
| tag_id | INTEGER | 外键 |

## CLI 命令设计

```bash
# 核心命令
meme sync [--source SOURCE] [--limit N] [--tag TAG]
meme search <关键词> [--source SOURCE] [--tag TAG] [--limit N]
meme random [--tag TAG] [--count N]
meme info <id|hash>
meme sources
meme export <id|hash|search-result> [--dest DIR]

# 标签管理
meme tag add <id> <tag>
meme tag remove <id> <tag>
meme tag list

# 统计
meme stats
```

### 输出格式
- 默认：简洁表格
- 选项：`--json` 脚本友好输出
- 预览：支持 iTerm2、kitty、Windows Terminal 图片显示

## QQ Bot 集成

### 技术栈
- NoneBot2
- NapCat / LLOneBot
- Python 3.10+

### 用户命令
```
/来张梗图 [关键词]        # 随机发送
/梗图搜索 <关键词>         # 搜索列表
/今日热图                 # 今日热门
/梗图标签                 # 列出标签
/标签 <标签名>             # 按标签发送
```

### 消息格式
- 搜索结果：转发消息，每条含图片+来源
- 用户回复序号获取原图

### 权限控制
- 白名单/黑名单配置
- 群/用户级别限制

## 技术栈

- **语言**: Python 3.10+
- **CLI框架**: Click / Typer
- **数据库**: SQLite
- **HTTP**: aiohttp / httpx
- **Bot框架**: NoneBot2
- **QQ协议**: NapCat / LLOneBot

## 后续实现计划

1. 项目初始化（Git、依赖）
2. 数据模型和存储层
3. Fetcher 采集器框架
4. CLI 核心命令
5. QQ Bot 插件
