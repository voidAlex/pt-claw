# PT Boost — 自动保种赚上传

## PT 刷流 — 自动保种赚上传（可选）

> ⚠️ **非必选项**。未配置则跳过。用户在 Step 0 被询问是否需要。

刷流是 PT 站常见的保号策略：自动下载免费（Freeleech）大包种子做种赚上传量，达到天数后自动删除换新种。

### 配置

用户在 Step 0 被询问刷流偏好，生成 `<skill-dir>/pt_boost.json`（模板：`templates/pt_boost.example.json`）：

```json
{
    "enabled": false,
    "global": {
        "boost_category": "boost",
        "boost_save_path": "<dedicated_download_path>",
        "max_seed_days": 7,
        "max_torrents": 20,
        "dead_seed_hours": 48,
        "delete_files": true
    },
    "sites": {
        "mteam": {
            "search_keyword": "",
            "freeleech_only": true,
            "exclude_hr": true,
            "sort_by": "seeders",
            "sort_order": "desc",
            "min_size_gb": 5,
            "max_size_gb": 200,
            "min_seeders": 5,
            "max_results": 50
        }
    },
    "schedule": "0 8 * * *",
    "per_run_add_limit": 5
}
```

qBittorrent 凭据统一从 `secrets.env` 读取（`QBITTORRENT_URL/USER/PASS`），不在此文件中重复存储。

| 字段 | 说明 |
|------|------|
| `global.boost_category` | qBittorrent 分类名，专用于刷流 |
| `global.boost_save_path` | 刷流专用下载目录（独立于正常下载） |
| `global.max_seed_days` | 做种多少天后自动删除 |
| `global.max_torrents` | 同时做种上限 |
| `global.dead_seed_hours` | 死种（stalledDL）超过此时长后自动清理（与 max_seed_days 独立） |
| `global.delete_files` | 删除种子时是否同时删除文件 |
| `sites.<site>.search_keyword` | 搜索关键词，空字符串表示拉最新种子列表 |
| `sites.<site>.freeleech_only` | 是否仅下载免费种子 |
| `sites.<site>.exclude_hr` | 是否排除 HR 种子 |
| `sites.<site>.min_size_gb` / `max_size_gb` | 种子大小范围 |
| `sites.<site>.min_seeders` | 最少做种人数 |
| `sites.<site>.max_results` | 每次搜索取前 N 个结果 |
| `per_run_add_limit` | 每次运行最多新增多少个种子 |

### 每日定时任务

> 📌 此任务仅在用户启用 PT 刷流时创建，不属于 Step 0 的三项核心任务。

固化在 cron，一条命令完成「清理→辅种检查→新增」全流程：

```python
cronjob(action='create',
    name="PT刷流",
    schedule="0 8 * * *",  # 每天早上8点
    prompt="运行 python3 scripts/pt_ratio_boost.py run，中文总结今日刷流情况后通知。",
    skills=["pt-claw"],
    deliver="origin"
)
```

### 每日执行逻辑（`pt_ratio_boost.py run`）

1. **删除过期种子**：做种超过 `max_seed_days` 天的 → 删除种子+文件
2. **清理死种**：下载中超过 2 天没进度的 → 删除
3. **新增刷流种**：
   - 计算剩余槽位（`max_torrents` - 当前数）
   - 从配置的站点搜索免费种子（mteam 走 API）
   - 按条件过滤：Freeleech > 大小范围 > 做种人数
   - 加入 qBittorrent，分类 `boost_category`，路径 `boost_save_path`
4. **输出状态**：当前种子数/上限、总上传/下载、分享率

### 脚本

- **[scripts/pt_ratio_boost.py](scripts/pt_ratio_boost.py)** — 刷流主脚本，三个子命令：
  - `python3 scripts/pt_ratio_boost.py run` — 完整刷流一次
  - `python3 scripts/pt_ratio_boost.py cleanup` — 仅清理过期
  - `python3 scripts/pt_ratio_boost.py status` — 查看刷流状态
