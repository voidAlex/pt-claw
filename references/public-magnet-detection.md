# 公开磁链检测规则

## 唯一标准：qB 标签

判断一个种子是否为"公开磁链"（public magnet），**唯一的可靠依据是 qBittorrent 标签**。

### ✅ 正确做法（TAG-ONLY）

```python
PUBLIC_TAGS = {"sukebei", "javbus"}

def is_public(torrent):
    torrent_tags = set(
        tag.strip() for tag in torrent.get("tags", "").split(",")
        if tag.strip()
    )
    return bool(torrent_tags & PUBLIC_TAGS)
```

### ❌ 错误做法（tracker URL 匹配）

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

## 为什么 tracker URL 匹配不可靠

PT 站种子通常同时包含：

1. **私有 tracker**（如 `https://pttime.org/announce.php?passkey=xxx`）— 种子专属
2. **公共 tracker**（如 `udp://tracker.opentrackr.org:1337/announce`）— 几乎所有 PT 种子都有

用公共 tracker URL 关键词判断，会导致 **所有 PT 种子被误判为公开种**。

## 2026-05-29 事故

- 原因：`公开磁链状态检查` cron 任务中的清理脚本用 tracker URL 匹配判断公开种
- 损失：约 520 个 PT 种子被误删
- 文件状态：`deleteFiles=false` 保住了数据文件，但 .torrent 文件从 BT_backup 被清除
- 恢复：从磁盘下载目录中扫描残留的 .torrent 文件，批量重新导入（共恢复 754 个）
- 修复：创建固定脚本 `scripts/qb_public_cleanup.py`，仅用标签判断
