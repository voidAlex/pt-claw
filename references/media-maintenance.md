# Media Maintenance — 重复检测 & 孤儿扫描

## 媒体库重复检测 — 深度扫描同名电影/剧集

### 用途

扫描媒体目录，检测重复下载的电影或同季剧集。排除多季/多集（正常收藏）。

### 扫描深度

不能只扫顶层目录——很多媒体嵌套在合集/系列文件夹内。需要 **2 层深度**：

```
movie/碟中谍系列/          ← 合集父目录（跳过）
movie/碟中谍系列/碟中谍1    ← 实际电影（纳入）
movie/碟中谍系列/碟中谍2    ← 实际电影（纳入）
```

### 归一化策略

剔除质量/编码/制作组标签，提取核心片名 + 年代/季号：

```python
def normalize(name):
    n = name.lower()
    # 剔标签
    for tag in ['2160p','1080p','720p','4k','uhd','hevc','h265','h264','x265','x264',
                '10bit','8bit','web-dl','bluray','blu-ray','remux','hdtv','bdrip',
                'dts-hd','dts','ddp','aac','truehd','atmos','hdr','dv','dovi',
                '60fps','30fps','complete','2audio','3audio','dual','multi']:
        n = re.sub(r'\b' + tag + r'\b', '', n, flags=re.I)
    # 去制作组后缀
    n = re.sub(r'@\w+.*$', '', n)
    n = re.sub(r'\s+[a-z]{2,6}$', '', n)
    n = re.sub(r'[\._\-\[\]\(\)]+', ' ', n).strip()
    return n
```

### 分组键

- **电影**：`{归一化名}|{年代}`（同名片不同年代不算重复）
- **剧集**：`{归一化名}|S{季号}`（不同季不算重复）
- 无季号的剧集/综艺 → 按归一化名分组

### 误报过滤

常见误报需人工排除：
- **`BDMV`**：所有蓝光原盘的子目录都叫 BDMV，不是重复
- **`CERTIFICATE`**：蓝光证书目录
- **合集父目录**：如「碟中谍系列」「蝙蝠侠三部曲」——内部有实际电影子目录，父目录本身不是媒体

### 排除项

- 文件大小 < 100MB 的跳过（nfo、封面、样本）
- 合集父目录跳过（其子目录会单独纳入）

### 参考实现

```python
import os, re
from collections import defaultdict

media_base = "/mnt/nas-media/video"

def get_size(path):
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try: total += os.path.getsize(os.path.join(root, f))
            except: pass
    return total

# 2 层深度扫描
all_items = []
for sd in ["movie", "tv", "show"]:
    top = os.path.join(media_base, sd)
    for item in os.listdir(top):
        fp = os.path.join(top, item)
        if os.path.isfile(fp) and os.path.getsize(fp) > 100*1024*1024:
            all_items.append((item, sd, fp))
        elif os.path.isdir(fp):
            # 深入一层：检查是否有媒体子目录
            for si in os.listdir(fp):
                sip = os.path.join(fp, si)
                if os.path.isdir(sip) and get_size(sip) > 100*1024*1024:
                    all_items.append((si, sd, sip))
            # 如果没有子目录，当前目录本身就是媒体
            sz = get_size(fp)
            if sz > 100*1024*1024:
                all_items.append((item, sd, fp))

# 分组 + 标记重复
movies = defaultdict(list)
for name, subdir, path in all_items:
    norm = normalize(name)
    year = extract_year(name)
    season = extract_season(name)
    if subdir == "movie":
        key = f"{norm}|{year}" if year else norm
        movies[key].append((name, subdir, path))
    else:
        key = f"{norm}|S{season:02d}" if season is not None else norm
        tv_shows[key].append((name, subdir, path))

duplicates = {k: v for k, v in movies.items() if len(v) > 1}
```

---

## Orphan Media Scan — 扫描未在 qB 中托管的媒体文件

### 场景

用户想手动恢复种子时，需要知道磁盘上有哪些内容不在 qBittorrent 中。本流程扫描媒体目录，交叉对比 qBittorrent 的 save_path/name，输出未托管的 Top N 项。

### 前置条件

- NAS 媒体通过 NFS 挂载到本机（如 `/mnt/nas-media/video/`）
- qBittorrent 可访问，cookie 文件可用
- qB 容器内的路径（如 `/media/video/movie`）与本机挂载路径（如 `/mnt/nas-media/video/movie`）可能不同——以本机可访问的路径为准

### 步骤

#### 1. 导出 qB 种子列表

```bash
# ⚠️ 不要用 source secrets.env（Cookie 值含 =，bash source 会误解析）
# 用 python 脚本代替，它们内部用 _load_env_file() 正确解析
python3 scripts/qb_monitor.py --full > /tmp/qb_torrents.json
```

#### 2. 扫描媒体目录

```bash
# 遍历所有媒体子目录，获取每个顶级文件夹/文件的大小
for d in /mnt/nas-media/video/movie /mnt/nas-media/video/tv /mnt/nas-media/video/show /mnt/nas-media/video/live; do
  [ -d "$d" ] && du -sh "$d"/* 2>/dev/null
done > /tmp/media_du.txt
```

#### 3. 交叉对比过滤

用 Python 脚本做模糊匹配：

```python
# 标准化：去除分隔符 + 质量标签（2160p/HEVC/DTS 等），只比内容词
def normalize(s):
    s = re.sub(r'[\._\-\[\]\(\)\s]+', ' ', s.lower())
    s = re.sub(r'\b(2160p|1080p|4k|hevc|h265|h264|avc|web-dl|bluray|uhd|bd|hd|dts|ddp|aac|truehd)\b', '', s, flags=re.I)
    return re.sub(r'\s+', ' ', s).strip()

# 匹配策略（按优先级）：
# 1. 目录名完全匹配 qB save_path 的 basename
# 2. 标准化后一方包含另一方
# 3. 单词重叠率 > 60%（针对中英文混合标题）
```

#### 4. 输出格式

**大小格式**：使用 `du -sk`（KB 精度），转为人类可读时保留 **两位小数**（如 `41.23G`，不是 `41G`）。

**路径格式**：使用 qBittorrent 容器内的原始路径（如 `/media/video/movie/xxx`），不要用本机 NFS 挂载路径（`/mnt/nas-media/video/movie/xxx`）。路径转换：`/mnt/nas-media/video/` → `/media/video/`。

**类型标签**：

| 标签 | 含义 |
|------|------|
| 📺 | 剧集合集（子目录含 S01/Season 或 SxxExx 模式） |
| 📁 | 文件夹/系列合集（非剧集结构的多文件目录） |
| 🎬 | 单文件（.mkv/.mp4 等） |

### 已知限制

- qB 容器内的路径可能与本机 NFS 挂载路径不同，以本机实际可访问路径为准
- 成人内容（`/9kg/` 路径）可能在 Docker volume 内，本机无法直接扫描
- `.nfo`、poster、sample 等小文件（<100MB）应过滤排除

### 模糊匹配陷阱

- **中文标题 + 英文标题混合**：qB 中存的是原种名（如 `大江大河之岁月如歌.Like.a.Flowing.River.S03.2024.2160p...`），磁盘目录可能是简化名。必须同时做包含匹配和词重叠匹配。
- **同一内容多个版本**：柯南剧场版有 `01-23.Pack` 和 `01-24.Pack` 两个版本都出现在磁盘上，模糊匹配后两者都可能被标记为"未在 qB 中"（如果 qB 只有其中一个）。这是预期行为——用户可能想恢复缺失的版本。
- **单文件 vs 目录**：REMUX 原盘有时是单个 .mkv，有时是 BDMV 目录结构。两者都按大小参与排序。
