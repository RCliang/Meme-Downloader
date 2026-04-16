# Meme Downloader

获取网络热门梗图和表情包的 CLI 工具，支持 QQ Bot 集成。

## 功能特性

- 🔄 从 Reddit、Imgur 等平台自动获取热门梗图
- 🔍 本地搜索和标签管理
- 🤖 QQ Bot 集成，聊天中随时发送
- 📦 SQLite 存储和自动去重

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

首次运行会自动创建 `~/.meme-downloader/` 目录和配置文件：

```bash
# 查看配置
cat ~/.meme-downloader/config.yaml
```

## CLI 使用

```bash
# 同步最新梗图
meme sync --source reddit --limit 50

# 搜索本地收藏
meme search "猫咪"

# 随机获取
meme random --tag 搞笑

# 查看详情
meme info <id>

# 查看统计
meme stats
```

## QQ Bot

### 前置要求

- 安装 [NapCat](https://github.com/NapNeko/NapCatQQ) 或 [LLOneBot](https://github.com/LLOneBot/LLOneBot)
- 配置 NoneBot2

### 使用

```python
# nonebot.py
from nonebot.default_config import *

HOST = "127.0.0.1"
PORT = 8080

ONEBOT_WS_URLS = ["ws://127.0.0.1:3001"]

custom_plugins = ["meme_downloader.bot"]
```

**Bot 命令：**
```
/来张梗图 [关键词]        # 随机发送
/梗图搜索 <关键词>         # 搜索列表
/今日热图                 # 今日热门
/梗图标签                 # 列出标签
/标签 <标签名>             # 按标签发送
```

## 项目结构

```
meme-downloader/
├── src/meme_downloader/
│   ├── cli/           # CLI 命令
│   ├── fetchers/      # 数据采集器
│   ├── db/            # 数据库操作
│   └── bot/           # QQ Bot 插件
├── docs/
│   └── plans/         # 设计文档
└── pyproject.toml     # 项目配置
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest
```

## License

MIT
