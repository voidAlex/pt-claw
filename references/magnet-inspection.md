# 磁力链接反查 — 不下载识别内容

## 适用场景

用户提供一个纯磁力链接（`magnet:?xt=urn:btih:<hash>`），想知道里面是什么内容，**但不下载**。

## 三步反查法

### Step 1：从 info hash 获取种子元数据

`itorrents.org` 是一个公共的 DHT 种子缓存，支持通过 info hash 直接获取 `.torrent` 元数据文件：

```bash
HASH="750e13a8300c2bd2cc26dde8b20826a2297ff794"
# 注意：hash 必须大写
curl -sL --max-time 15 -o /tmp/inspect.torrent \
  "https://itorrents.org/torrent/${HASH}.torrent"
```

验证是否成功：
```bash
file /tmp/inspect.torrent
# 期望输出: /tmp/inspect.torrent: BitTorrent file
```

### Step 2：从种子文件中提取文件名

种子文件是 bencoded 格式，用 `strings` 即可快速提取可读文本：

```bash
strings /tmp/inspect.torrent | head -50
```

输出中通常能看到：
- 种子名称（在 `d…name` 之后）
- 文件名列表（`.mp4`, `.mkv`, `.txt` 等）
- 这通常能直接暴露番号或影片标题

### Step 3：根据文件名类型获取详细信息

**如果是 JAV 番号**（如 `IPBZ-017.mp4`）：
```bash
# 使用本地 javbus-api（若已部署）
curl -s --max-time 5 "http://localhost:8922/api/movies/<CODE>" | python3 -m json.tool
```
返回：标题、发行日期、导演、系列、演员列表、制作公司。

**如果是影视名称**：用 `pt_search.py` 全站搜索影片标题获取详情页。

## 备选方案

| 方案 | 命令 | 适用场景 |
|------|------|---------|
| M-Team API 搜索 hash | `mteam_api.py search "<hash>"` | 种子可能在馒头 |
| JavBus 直接爬取 | `javbus_magnet.py <CODE> --scrape` | javbus-api 不可用时 |
| btdig/solidtorrents 搜索 | `curl` 搜索 hash | itorrents 无缓存时 |

## 注意

- itorrents.org 偶尔会超时/无缓存 → 重试一次或换备选方案
- `strings` 提取的是原始 bencode 中的字符串片段，不是完整结构化数据
- 此流程**不触发下载确认闸门** — 用户明确要求「仅检查不下载」时，不展示大小/做种/路径等下载信息
- 清洁：检查完成后 `rm /tmp/inspect.torrent`
