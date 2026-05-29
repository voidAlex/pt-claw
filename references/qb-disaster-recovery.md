# qBittorrent 灾难恢复手册

## 2026-05-29 事故记录

**事故**：`公开磁链状态检查` cron 用 tracker URL 关键词误判 PT 种为公开种，删除约 520 个种子（`deleteFiles=false`，文件未丢）。

**根因**：`is_public()` 函数检查 tracker URL 中是否含 `openbittorrent`/`opentracker` 等关键词，但 PT 种子也内置了这些公共 tracker。

**修复**：改为 TAG-ONLY 判断（sukebei/javbus 标签），固定脚本 `scripts/qb_public_cleanup.py`。

## 恢复优先级

恢复种子到 qBittorrent 的数据源，按可靠性排序：

### 层级 1：磁盘上的 .torrent 文件（最可靠）

扫描下载目录，找到与数据文件同目录的 `.torrent` 文件。这些文件与磁盘数据**完全匹配**。

路径映射（NFS → qB 容器）：`<NAS_MEDIA_PATH>/video/movie` → `/media/video/movie`、`<NAS_DOWNLOAD_PATH>` → `/downloads`、`<NAS_ADULT_PATH>/javdb-top250` → `<QB_ADULT_PATH>`。

**导入方法**：`add` → 立即 `setLocation`（multipart `?savepath=` 会被忽略）。setLocation 前必须先 pause（HTTP 409 意味着种子在活跃传输中）。

### 层级 2：PT 站原始种子（高可靠）

从各 PT 站的「我的下载历史 / snatchlist」页面下载**原来用过的那个 .torrent**。内部文件结构与磁盘数据完全一致，导入后 qB 自动校验。

### 层级 3：PT 站搜索匹配（低可靠，有风险）

按文件名+大小在 PT 站搜索匹配的种子。

**⚠️ 致命风险**：PT 站的种子内部文件夹名可能与磁盘不同（如种子期望 `The.Knockout/`，磁盘是 `狂飙/`），导致 qB **重新下载**而非校验已有数据。导入后必须验证：`progress > 0%` 且 `dlspeed > 0` → 说明在重新下载，应立即删除。

## 公开内容过滤

恢复时必须跳过：`<NAS_ADULT_PATH>/其他/`（公开源内容），无 .torrent 文件的裸视频文件。

## 恢复验证清单

- save_path 指向正确的容器路径（非 NFS 路径）
- 没有种子正在重新下载（dlspeed > 0 且 progress < 10%）
- 没有导入公开磁链
- 种子状态为 checkingDL → stalledUP/uploading（校验通过）
