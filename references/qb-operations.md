# qBittorrent Operations — 推送、清理、恢复

## 连接与认证

qBittorrent 地址、用户名、密码从环境变量读取：

| 变量 | 说明 |
|------|------|
| `QBITTORRENT_URL` | Web UI 地址（含端口） |
| `QBITTORRENT_USER` | 登录用户名 |
| `QBITTORRENT_PASS` | 登录密码 |

所有脚本通过 `_env()` 读取，不从 skill 内部硬编码。

**分类与路径 — 动态读取**：禁止在 skill 中硬编码分类名和路径，使用 API 动态读取：

```bash
# 读取用户实际分类
curl -b <cookie> '<QBITTORRENT_URL>/api/v2/torrents/categories'

# 示例返回：{"电影": {"savePath": "/path/to/movies"}, "电视剧": {...}}
```

Agent 在 Step 4 推送下载时，先调此 API 获取真实分类列表，再匹配或让用户选择。

## 关键 API

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/v2/auth/login` | POST | 登录 |
| `/api/v2/torrents/add` | POST | 添加种子 |
| `/api/v2/torrents/addTags` | POST | 打标签 |
| `/api/v2/torrents/categories` | GET | 读取分类 |
| `/api/v2/torrents/setCategory` | POST | 修改分类 |
| `/api/v2/torrents/setLocation` | POST | 修改路径 |
| `/api/v2/torrents/info` | GET | 查询种子状态 |
| `/api/v2/torrents/delete` | POST | 删除种子 |

## 推送两步法

### 问题

PT 站的 `download.php?id=X` 需要 PT 站的 Cookie 才能访问。如果用 `urls=<download_url>` 方式把链接直接传给 qBittorrent，qB 返回 `Ok.` 但实际不会添加任何任务——因为 qB 自己去拉 URL 时没有 PT Cookie，被拒了。

**这是静默失败**：API 返回成功，qB 列表里却看不到新种子。

### 正确流程（五步）

#### Step 1: 用 PT Cookie 下载 .torrent 到本地

```python
import urllib.request

pt_cookie = "<从 .env 读取>"
dl_url = "https://pt.example.com/download.php?id=123"

req = urllib.request.Request(
    dl_url,
    headers={"Cookie": pt_cookie, "User-Agent": "Mozilla/5.0"}
)
with urllib.request.urlopen(req, timeout=30) as resp:
    torrent_data = resp.read()

# 验证是 torrent 文件
assert torrent_data[:2] == b'd8', "Not a torrent file!"

with open('/tmp/torrent.torrent', 'wb') as f:
    f.write(torrent_data)
```

#### Step 2: 登录 qB → multipart 上传本地文件

```python
import http.cookiejar, urllib.request, os, binascii

qb_url = "http://<QB_HOST>"
qb_user = "<user>"
qb_pass = "<pass>"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
login_data = f"username={urllib.parse.quote(qb_user)}&password={urllib.parse.quote(qb_pass)}".encode()
opener.open(f"{qb_url}/api/v2/auth/login", data=login_data)

boundary = '----QB' + binascii.hexlify(os.urandom(8)).decode()
with open('/tmp/torrent.torrent', 'rb') as f:
    file_bytes = f.read()

body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="torrents"; filename="download.torrent"\r\n'
    f'Content-Type: application/x-bittorrent\r\n\r\n'
).encode() + file_bytes + f'\r\n--{boundary}--\r\n'.encode()

add_req = urllib.request.Request(
    f"{qb_url}/api/v2/torrents/add",
    data=body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)
opener.open(add_req)
```

#### Step 3: 验证（必做！）

```python
with opener.open(f"{qb_url}/api/v2/torrents/info?sort=added_on&reverse=true&limit=5") as resp:
    recent = json.loads(resp.read())
    print(f"Latest: {[t['name'][:40] for t in recent]}")
```

#### Step 4: 设置分类和路径

```python
with opener.open(f"{qb_url}/api/v2/torrents/categories") as resp:
    cats = json.loads(resp.read())

cat_data = f"hashes={hash}&category={urllib.parse.quote('<分类名>')}".encode()
opener.open(f"{qb_url}/api/v2/torrents/setCategory", data=cat_data)

path_data = f"hashes={hash}&location={urllib.parse.quote('<目标路径>')}".encode()
opener.open(f"{qb_url}/api/v2/torrents/setLocation", data=path_data)
```

#### Step 5: 打站点标签（必须！）

```python
# 标签 = source/site_id: mteam/pttime/btschool/carpt/hdfans/1ptba/soulvoice/zmpt/sukebei/javbus
tag_data = f"hashes={hash}&tags={urllib.parse.quote('pttime')}".encode()
opener.open(f"{qb_url}/api/v2/torrents/addTags", data=tag_data)
```

或用 `qb_add.py` 一步完成：`python3 scripts/qb_add.py "magnet:..." --tags sukebei`

**手动 curl 补标签**：

```bash
HASH=$(curl -s -b /tmp/qb_cookies.txt \
  "http://<QB_HOST>/api/v2/torrents/info?sort=added_on&reverse=true&limit=5" \
  | python3 -c "import sys,json;[print(t['hash']) for t in json.load(sys.stdin) if '<关键词>' in t['name']]")
curl -s -b /tmp/qb_cookies.txt -X POST \
  "http://<QB_HOST>/api/v2/torrents/addTags" \
  --data-urlencode "hashes=$HASH" --data-urlencode "tags=sukebei"
```

### 常见翻车场景

1. **分类名不匹配**：qB 里叫"电视剧"，却传了 `category=tv` → 分类为空
2. **multipart upload 不认 query param**：`/torrents/add?category=电视剧` 的 `?category=` 在 multipart 上传时可能不生效 → 事后 `setCategory` + `setLocation` 修正
3. **Cookie 过期**：.torrent 下载返回登录页 HTML 而不是 bencode → Cookie 过期
4. **代理干扰**：下载 .torrent 走代理可能被 PT 站拒绝（403）→ 先试直连
5. **忘记打标签**：没打站点标签 → 后续无法按来源筛选，比率管理困难

## 公开磁链检测规则

### 唯一标准：qB 标签

判断一个种子是否为"公开磁链"（public magnet），**唯一的可靠依据是 qBittorrent 标签**。

#### 正确做法（TAG-ONLY）

```python
PUBLIC_TAGS = {"sukebei", "javbus"}

def is_public(torrent):
    torrent_tags = set(
        tag.strip() for tag in torrent.get("tags", "").split(",")
        if tag.strip()
    )
    return bool(torrent_tags & PUBLIC_TAGS)
```

#### 错误做法（tracker URL 匹配）

```python
# DANGEROUS — DO NOT USE
PUBLIC_TRACKER_KEYWORDS = [
    "openbittorrent", "opentracker", "publicbt",
    "tracker.open", "tracker.coppersurfer",
]

def is_public(torrent):
    for tr in get_trackers(torrent["hash"]):
        for kw in PUBLIC_TRACKER_KEYWORDS:
            if kw in tr["url"].lower():
                return True  # FALSE POSITIVE!
    return False
```

### 为什么 tracker URL 匹配不可靠

PT 站种子通常同时包含：

1. **私有 tracker**（如 `https://pttime.org/announce.php?passkey=xxx`）— 种子专属
2. **公共 tracker**（如 `udp://tracker.opentrackr.org:1337/announce`）— 几乎所有 PT 种子都有

用公共 tracker URL 关键词判断，会导致 **所有 PT 种子被误判为公开种**。

### 2026-05-29 事故

- **原因**：`公开磁链状态检查` cron 任务中的清理脚本用 tracker URL 匹配判断公开种
- **根因**：`is_public()` 函数检查 tracker URL 中是否含 `openbittorrent`/`opentracker` 等关键词，但 PT 种子也内置了这些公共 tracker
- **损失**：约 520 个 PT 种子被误删
- **文件状态**：`deleteFiles=false` 保住了数据文件，但 .torrent 文件从 BT_backup 被清除
- **恢复**：从磁盘下载目录中扫描残留的 .torrent 文件，批量重新导入（共恢复 754 个）
- **修复**：创建固定脚本 `scripts/qb_public_cleanup.py`，仅用标签判断

## 灾难恢复

> 2026-05-29 事故详情见上方「公开磁链检测规则」章节。

### 恢复优先级

恢复种子到 qBittorrent 的数据源，按可靠性排序：

#### 层级 1：磁盘上的 .torrent 文件（最可靠）

扫描下载目录，找到与数据文件同目录的 `.torrent` 文件。这些文件与磁盘数据**完全匹配**。

路径映射（NFS → qB 容器）见下方「NAS 卷映射」章节。

**导入方法**：`add` → 立即 `setLocation`（multipart `?savepath=` 会被忽略）。setLocation 前必须先 pause（HTTP 409 意味着种子在活跃传输中）。

#### 层级 2：PT 站原始种子（高可靠）

从各 PT 站的「我的下载历史 / snatchlist」页面下载**原来用过的那个 .torrent**。内部文件结构与磁盘数据完全一致，导入后 qB 自动校验。

#### 层级 3：PT 站搜索匹配（低可靠，有风险）

按文件名+大小在 PT 站搜索匹配的种子。

**致命风险**：PT 站的种子内部文件夹名可能与磁盘不同（如种子期望 `The.Knockout/`，磁盘是 `狂飙/`），导致 qB **重新下载**而非校验已有数据。导入后必须验证：`progress > 0%` 且 `dlspeed > 0` → 说明在重新下载，应立即删除。

### 公开内容过滤

恢复时必须跳过：`<NAS_ADULT_PATH>/其他/`（公开源内容），无 .torrent 文件的裸视频文件。

### 恢复验证清单

- save_path 指向正确的容器路径（非 NFS 路径）
- 没有种子正在重新下载（dlspeed > 0 且 progress < 10%）
- 没有导入公开磁链
- 种子状态为 checkingDL → stalledUP/uploading（校验通过）

## NAS 卷映射

### NFS 挂载点 → qB 容器路径

| NFS 挂载（Hermes 主机） | qB 容器路径 | 内容 |
|---|---|---|
| `<NAS_MOUNT_MEDIA>/video/movie` | `/media/video/movie` | 电影 |
| `<NAS_MOUNT_MEDIA>/video/tv` | `/media/video/tv` | 电视剧 |
| `<NAS_MOUNT_MEDIA>/video/live` | `/media/video/live` | 纪录片 |
| `<NAS_MOUNT_MEDIA>/video/show` | `/media/video/show` | 综艺 |
| `<NAS_MOUNT_MEDIA>/video/sport` | `/media/video/sport` | 体育 |
| `<NAS_MOUNT_MEDIA>/video/music-live` | `/media/video/music-live` | 音乐现场 |
| `<NAS_MOUNT_DOWNLOADS>` | `/downloads` | qB 默认下载路径 |
| `<NAS_ADULT_PATH>/javdb-top250` | `<QB_ADULT_PATH>` | 成人内容 |
| `<NAS_ADULT_PATH>/其他` | `<QB_ADULT_OTHER_PATH>` | 其他成人（公开源）⚠️ SKIP |
| `<NAS_MOUNT_QB>/config` | `/config` | qB 配置目录 |
| `<NAS_MOUNT_QB>/config/qBittorrent/BT_backup` | — | .torrent 备份文件 |

### NAS NFS 挂载命令

```bash
sudo mount -t nfs <NAS_IP>:/<VOL_MEDIA> <NAS_MOUNT_MEDIA>
sudo mount -t nfs <NAS_IP>:/<VOL_DOWNLOADS> <NAS_MOUNT_DOWNLOADS>
sudo mount -t nfs <NAS_IP>:/<VOL_SYSTEM> <NAS_MOUNT_SYSTEM>
sudo mount -t nfs <NAS_IP>:/<VOL_DOCKER> <NAS_MOUNT_QB>
```

### 导入路径规则

导入 .torrent 文件时，`savepath` 使用**容器路径**（上表右列），不是 NFS 路径。multipart upload 忽略 `?savepath=` query param — 必须在 `add` 之后调用 `setLocation` API。

### 分层恢复策略

1. **本地 .torrent 文件** — 扫描数据目录中的 `.torrent` 文件，用正确容器路径导入
2. **PT snatchlist** — 用户从 PT 站下载历史重新下载原始 .torrent（保证完全匹配）
3. **PT 站搜索** — 最后手段；.torrent 内部结构可能与磁盘不匹配，导入后必须验证 qB 在校验而非重新下载
4. **公开内容** — 跳过 PT 恢复，这些是来自公开源的磁力链接
