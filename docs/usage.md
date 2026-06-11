# 使用方法

## 安装

```bash
git clone https://github.com/yourusername/meme-downloader.git
cd meme-downloader

# 基础安装
pip install -e .

# 可选：QQ Bot 支持
pip install -e ".[bot]"

# 可选：向量相似搜索（需要 Milvus + DashScope）
pip install -e ".[vector]"

# 开发依赖
pip install -e ".[dev]"
```

首次运行自动创建 `~/.meme-downloader/` 目录和配置文件。

## 数据源

| 来源 | 说明 | 需要认证 |
|------|------|---------|
| `gengtu` | 梗图网，中文梗图，带 AI 描述 | 否（cloudscraper 绕过 Cloudflare） |
| `reddit` | Reddit 热门梗图子版块 | 否（公开 JSON API） |
| `imgur` | Imgur 热门梗图 | 需要 `client_id` |

## CLI 命令

### 同步梗图

```bash
# 从所有已配置来源随机获取
meme sync

# 从指定来源获取
meme sync --source gengtu
meme sync --source reddit --limit 50

# 限制数量
meme sync --source gengtu --limit 10

# 按关键词搜索获取（仅 gengtu 来源，自动翻页）
meme sync --source gengtu --keyword "猫咪"
meme sync -s gengtu -k "程序员" -n 100

# 自动打标签
meme sync --source gengtu --tag 搞笑

# 批量获取（去重机制保证不会重复下载）
for i in $(seq 1 10); do meme sync --source gengtu --limit 20; done

# 批量搜索获取
for i in $(seq 1 5); do meme sync --source gengtu -k "猫咪" --limit 20; done
```

### 搜索本地收藏

```bash
# 按关键词搜索标题
meme search "猫咪"

# 按来源过滤
meme search "猫咪" --source gengtu

# 按标签过滤
meme search "猫咪" --tag 搞笑

# JSON 格式输出（方便脚本处理）
meme search "猫咪" --json
```

### 随机获取

```bash
# 随机一张
meme random

# 随机多张
meme random --count 5

# 按标签随机
meme random --tag 搞笑
```

### 查看详情

```bash
# 按 ID 查询
meme info 42

# 按哈希值查询
meme info abc123def456
```

### 标签管理

```bash
# 添加标签
meme tag add 42 搞笑

# 移除标签
meme tag remove 42 搞笑

# 列出所有标签
meme tag list
```

### 导出图片

```bash
# 导出到指定目录
meme export 42 --dest ./output
```

### 查看统计

```bash
meme stats
```

### 列出数据源

```bash
meme sources
```

## 向量相似搜索（可选功能）

需要安装 `pip install -e ".[vector]"` 并配置 `~/.meme-downloader/config.yaml`：

```yaml
vector:
  enabled: true
  embedding:
    api_key: "your-dashscope-api-key"
    model: "text-embedding-v3"
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dimensions: 1024
    batch_size: 20
  milvus:
    uri: "http://localhost:19530"
    token: ""
    collection: "meme_embeddings"
    index_type: "HNSW"
```

配置完成后，`meme sync` 会自动为带描述的梗图生成 embedding。

```bash
# 语义搜索：用自然语言描述找相似梗图
meme similar "一只猫坐在键盘上"
meme similar "猫咪" --source gengtu --limit 5
meme similar "程序员调试代码" --json

# 回填已有梗图到向量库
meme index --source gengtu --limit 1000
```

## QQ Bot

参见 [README.md](../README.md) 中的 QQ Bot 章节。

## 数据存储

```
~/.meme-downloader/
├── memes/              # 图片文件（文件名 = SHA256 哈希）
├── metadata.db         # SQLite 元数据数据库
├── config.yaml         # 配置文件
└── logs/               # 日志目录
```

## 常用选项

| 选项 | 短选项 | 说明 |
|------|--------|------|
| `--source` | `-s` | 指定数据来源 |
| `--limit` | `-n` | 限制数量 |
| `--tag` | `-t` | 指定标签 |
| `--keyword` | `-k` | 搜索关键词（gengtu） |
| `--json` | | JSON 格式输出 |
