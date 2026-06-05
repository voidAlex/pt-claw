# 通过 Info Hash 识别种子内容（不下载）

当用户发来一个 magnet 链接问"这是什么"时，按以下流程在不实际下载文件内容的情况下识别：

## 流程

### 1. 从 magnet 提取 info hash

```
magnet:?xt=urn:btih:750e13a8300c2bd2cc26dde8b20826a2297ff794
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                        info hash (40 hex chars)
```

### 2. 通过 itorrents.org 获取 .torrent 元数据

```bash
curl -sL --max-time 15 -o /tmp/test_torrent.torrent \
  "https://itorrents.org/torrent/<UPPERCASE_HASH>.torrent"
file /tmp/test_torrent.torrent  # 确认是 BitTorrent file
```

### 3. 提取可读文本

```bash
strings /tmp/test_torrent.torrent | head -50
```

通常前几行就能看到：
- `name` — 种子名称（通常是番号或片名）
- `files` — 文件列表（含 .mp4/.mkv 文件名）
- `piece length` — 分块大小

### 4. 如果是 JAV 番号 → 查 javbus-api

```bash
curl -s --max-time 5 "http://localhost:8922/api/movies/<番号>" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({k:d.get(k) for k in ['title','date','director','studio','stars'] if k in d}, indent=2, ensure_ascii=False))"
```

返回标题、发行日期、导演、制作公司、演员列表。

### 5. 如果是国产内容 → 尝试 PT 搜索 + Sukebei

用 `pt_search.py` 搜索片名/演员名，必要时加 `--adult`。PT 无结果时回退到 `sukebei_search.py`。

## 备选方案

如果 itorrents.org 不可用，尝试：
- `https://bt4g.org/search?q=<hash>`
- `https://btdig.com/search?q=<hash>`
- `https://solidtorrents.to/api/v1/search?query=<hash>`

## 注意

- 仅获取元数据（torrent 文件小，几 KB），**不下载实际内容**
- itorrents.org 对大小写不敏感，但某些镜像可能区分
- `strings` 提取的文本可能有乱码（bencode 二进制编码），但文件名/片名通常是可读的 ASCII/UTF-8
