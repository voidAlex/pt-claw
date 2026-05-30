# 媒体库重复检测 — 深度扫描同名电影/剧集

## 用途

扫描媒体目录，检测重复下载的电影或同季剧集。排除多季/多集（正常收藏）。

## 扫描深度

不能只扫顶层目录——很多媒体嵌套在合集/系列文件夹内。需要 **2 层深度**：

```
movie/碟中谍系列/          ← 合集父目录（跳过）
movie/碟中谍系列/碟中谍1    ← 实际电影（纳入）
movie/碟中谍系列/碟中谍2    ← 实际电影（纳入）
```

## 归一化策略

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

## 分组键

- **电影**：`{归一化名}|{年代}`（同名片不同年代不算重复）
- **剧集**：`{归一化名}|S{季号}`（不同季不算重复）
- 无季号的剧集/综艺 → 按归一化名分组

## 误报过滤

常见误报需人工排除：
- **`BDMV`**：所有蓝光原盘的子目录都叫 BDMV，不是重复
- **`CERTIFICATE`**：蓝光证书目录
- **合集父目录**：如「碟中谍系列」「蝙蝠侠三部曲」——内部有实际电影子目录，父目录本身不是媒体

## 排除项

- 文件大小 < 100MB 的跳过（nfo、封面、样本）
- 合集父目录跳过（其子目录会单独纳入）

## 参考实现

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

## 相关文档

- [orphan-media-scan.md](orphan-media-scan.md) — 磁盘孤儿媒体扫描（不在 qB 中的文件）
