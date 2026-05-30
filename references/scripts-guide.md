# Scripts Guide — 用法速查

## Scripts

所有脚本位于 `scripts/` 目录，配置文件路径见脚注¹。

### pt_search.py — 多站搜索（8 站，含馒头 API）

```bash
# 单站
python3 scripts/pt_search.py "流浪地球2" --site pttime --limit 5

# 全站（需代理的站自动走 PT_PROXY，无需手动包装）
python3 scripts/pt_search.py "流浪地球2" --limit 5

# PTTime 成人区（按番号/关键词）
python3 scripts/pt_search.py "SONE-833" --site pttime --adult --limit 10

# PTTime 成人区（按演员名）
python3 scripts/pt_search.py "" --site pttime --adult --actor "浅野心" --limit 10
```

**接入方式**：
- **M-Team**: **仅限 REST API**（`x-api-key` 认证，`MTEAM_API_KEY` 环境变量）。**禁止使用 Cookie 登录——会封号。** 搜索 ✅，下载 ✅（genDlToken）
- **其他 7 站**: Cookie 直连或代理（从 `PT_COOKIE_<SITE>` 环境变量读取，`needs_proxy` 站点自动走 `PT_PROXY`）
- **BTSchool/CarPT/SoulVoice/织梦**: NexusPHP 站，cookie 绑定登录 IP，必须走与浏览器相同出口的代理才能用

### qb_add.py — 添加到 qBittorrent（含站点标签 + 文件选择）

```bash
# 公开磁链 — 列出文件供用户选择（推荐）
python3 scripts/qb_add.py "magnet:?xt=urn:btih:ABCDEF..." --tags sukebei --list-files
# 用户确认后，选择要下载的文件
python3 scripts/qb_add.py --select-files <HASH> --keep=0,3,5

# 公开磁链 — 自动选最大视频文件（批量场景兜底）
python3 scripts/qb_add.py "magnet:?xt=urn:btih:ABCDEF..." --tags sukebei --max-video

# PT 种子不需要文件选择（PT 站一般只有正片）
python3 scripts/qb_add.py "https://pt.example.com/download.php?id=123" --category "电影" --tags pttime

# stdin JSON 模式（支持 max_video 字段）
echo '{"magnet": "...", "category": "<分类名>", "save_path": "<路径>", "tags": ["sukebei"], "max_video": true}' | python3 scripts/qb_add.py --stdin
```

**公开磁链文件选择（推荐流程）**：
1. `--list-files`：添加种子（暂停）→ 等元数据 → 列出所有文件（名称/大小/类型）→ 返回 JSON
2. Agent 展示文件列表给用户确认要下哪些
3. `--select-files <HASH> --keep=0,3,5`：跳过未选文件 → 恢复下载

**`--max-video` 自动模式（兜底）**：添加种子暂停 → 等元数据 → 三级策略选正片：
1. 文件名含番号（如 `MIMK-267`）→ 取最大的匹配文件
2. 排除含广告关键词的文件（ad/sample/preview/广告/宣传/预告等）→ 取最大的
3. 兜底取最大视频文件

stdin JSON 传 `"code": "MIMK-267"` 可辅助精确匹配。字幕文件（.srt/.ass）同名校验后保留。PT 站种子不需要此参数（PT 资源干净）。
### download_history.py — 下载历史追踪

```bash
# 添加记录
python3 scripts/download_history.py add --code MIMK-267 --title "xxx" --source sukebei

# 检查是否已下载过
python3 scripts/download_history.py check --code MIMK-267
# → {"exists": true, "code": "MIMK-267"}

# 批量过滤：从 stdin 读 code 列表，只输出未下载过的
echo -e "MIMK-267\nNEW-001" | python3 scripts/download_history.py filter
# → NEW-001

# 列出全部历史
python3 scripts/download_history.py list
```

### qb_monitor.py — qBittorrent 全功能查询

```bash
# 默认：24h内完成的下载
python3 scripts/qb_monitor.py

# 完整状态报告（全状态、速度、死种、近期完成）
python3 scripts/qb_monitor.py --full

# 按番号过滤
python3 scripts/qb_monitor.py --full --codes "ROYD-318,JUFE-622"

# 按标签过滤
python3 scripts/qb_monitor.py --tags sukebei,javbus

# 按状态过滤
python3 scripts/qb_monitor.py --states downloading,stalledDL

# 删除匹配的种子（保留文件）——先查后删
python3 scripts/qb_monitor.py --delete --codes "ROYD-318" --check   # 只预览不删
python3 scripts/qb_monitor.py --delete --codes "ROYD-318"           # 确认后删除
python3 scripts/qb_monitor.py --delete --tags sukebei --states stalledDL --check
```

> ⚠️ **`--tracker` 参数注意**：`qb_monitor.py --tracker <file>` 的 `_read_tracker()` 期望 tracker 文件是单个 epoch 时间戳整数，不是 hash 列表。如果文件包含 hash（如 cron 的 `pt_completed_last.txt`），会解析失败退回 epoch 0，展示全部完成记录。Cron 进度检查应使用 hash-based 方式（见 [references/cron-patterns.md](references/cron-patterns.md)），不用 `--tracker`。

### javbus_star.py — 演员片单交叉对比

```bash
# 搜索演员（支持中/日文名），交叉对比 JF + 下载历史
python3 scripts/javbus_star.py "彩月七緒"

# 只显示缺失的最新 N 部
python3 scripts/javbus_star.py "浅野こころ" --top 10

# 用 star ID 直接查询
python3 scripts/javbus_star.py --star-id 11wm
```

输出：已有（JF或已下载）和缺失的影片列表，按日期排序。

### qb_backup.py / qb_restore.py — 删种备份与恢复

```bash
# 查看最近50条备份
python3 scripts/qb_backup.py --list

# 查看最近备份（格式化）
python3 scripts/qb_restore.py --list

# 恢复指定种子（按hash前缀）
python3 scripts/qb_restore.py --restore <hash_prefix>

# 恢复最近一次删除的种子
python3 scripts/qb_restore.py --last

# 批量恢复（按删除原因）
python3 scripts/qb_restore.py --restore-all --reason public_cleanup
python3 scripts/qb_restore.py --restore-all --reason manual_delete
python3 scripts/qb_restore.py --restore-all --reason boost_aged

# 清除备份记录
python3 scripts/qb_backup.py --clear
```

`qb_public_cleanup.py`、`qb_monitor.py --delete`、`pt_ratio_boost.py` 删除种子前自动调用 `backup_from_torrents()`，将 hash/名称/路径/标签/分类 **加上 .torrent 文件** 备份到 `torrent_backups/`，元数据写入 `pt_deleted_backup.json`（保留最近 500 条）。

**恢复链路**：`qb_restore.py` 从备份恢复种子到 qBittorrent。支持按 hash 单个恢复、最近恢复、按原因批量恢复。恢复时重新上传 .torrent 文件并应用原始标签/分类/路径。无 .torrent 文件的条目会打印搜索关键词供手动恢复。

**确认机制**：三个删种脚本均支持 `--check` 参数，只查不删，展示将被删除的种子清单，等用户确认后再执行实际删除。用法：

```bash
python3 scripts/qb_public_cleanup.py --check   # 公开磁链：预览待删除清单
python3 scripts/qb_monitor.py --delete --tags javbus --check  # qb_monitor：预览匹配项
python3 scripts/pt_ratio_boost.py cleanup --check  # 刷流清理：预览过期种子
```

### jf_query.py — Jellyfin 查询

```bash
# 演员排名
python3 scripts/jf_query.py --list stars --top 20

# 搜索
python3 scripts/jf_query.py --search "浅野"

# 检查番号
python3 scripts/jf_query.py --check "ROYD-318"
```

### javbus_magnet.py — JavBus 磁链获取

```bash
# 通过 javbus-api（推荐，结构化数据）
python3 scripts/javbus_magnet.py SNOS-151 --api http://localhost:8922

# 裸爬模式（无 javbus-api 时）
python3 scripts/javbus_magnet.py SNOS-151 --scrape
```

输出 JSON 数组，每条含 title、magnet、size、isHD、hasSubtitle、shareDate。内置广告过滤和垃圾磁链排除。

### sukebei_search.py — Sukebei Nyaa RSS 搜索

```bash
python3 scripts/sukebei_search.py SNOS-151              # 搜索
python3 scripts/sukebei_search.py SNOS-151 --limit 5    # 限制条数
```

通过 RSS 搜索 Sukebei Nyaa，返回 JSON（seeders/leechers/size/magnet/title）。内置广告去重和评分排序。

### mteam_api.py — M-Team API 客户端

`pt_search.py` 和 `pt_ratio_boost.py` 的内部依赖，也可独立使用：

```bash
# 搜索
python3 scripts/mteam_api.py search "关键词" --key $MTEAM_API_KEY --limit 25

# 获取签名下载 URL
python3 scripts/mteam_api.py download <torrent_id> --key $MTEAM_API_KEY
```

API 详细文档见 [references/mteam-api.md](references/mteam-api.md)。

### connectivity_check.py — 全服务连接测试

```bash
python3 scripts/connectivity_check.py              # 测试所有服务
python3 scripts/connectivity_check.py --quick       # 跳过 PT 站（仅测 qB/JF/M-Team/代理）
python3 scripts/connectivity_check.py --site btschool  # 只测某个站
python3 scripts/connectivity_check.py --json        # JSON 格式输出
```

实际发起 HTTP 请求测试每个外部服务：qBittorrent 登录、M-Team API、两个 Jellyfin 实例、javbus-api Docker、PT_PROXY 代理、8 个 PT 站 Cookie 有效性。`env_check.sh` 只检查变量是否存在，此脚本验证连接和认证是否真正可用。

`needs_proxy=True` 站点走代理访问；`needs_proxy=False` 站点先直连，失败自动代理重试。`--keepalive` 模式访问各站首页刷新 session，cookie 失败时自动触发 CookieCloud 同步。

### cookie_sync.py — CookieCloud Cookie 同步（可选）

```bash
python3 scripts/cookie_sync.py                    # 同步所有 PT 站
python3 scripts/cookie_sync.py --dry-run           # 预览不同步
python3 scripts/cookie_sync.py --site btschool     # 只同步一个站
```

从 CookieCloud 服务端拉取浏览器 Cookie，解密后更新 `secrets.env` 中的 `PT_COOKIE_*`（M-Team 除外，因 M-Team 使用 API Key 认证，不同步 cookie）。需要 `secrets.env` 中配置 `COOKIE_CLOUD_HOST`/`UUID`/`PASS`（可选，不配置则跳过）。

**依赖**：`python3-cryptography`（系统包 `apt install python3-cryptography`，或 `pip install cryptography`）。

**CookieCloud 部署**（可选）：

1. Docker 部署服务端：
   ```bash
   mkdir -p ~/cookiecloud
   cp templates/docker-compose.cookiecloud.yml ~/cookiecloud/docker-compose.yml
   docker compose -f ~/cookiecloud/docker-compose.yml up -d
   ```

2. 浏览器安装 [CookieCloud 扩展](https://github.com/easychen/CookieCloud)（[Chrome](https://chrome.google.com/webstore/detail/cookiecloud/ffjiejobkoibkjlhjnlgmcnnigeelbdl) / [Edge](https://microsoftedge.microsoft.com/addons/detail/cookiecloud/bffenpfpjikaeocaihdonmgnjjdpjkeo)）

3. 扩展中填入服务器地址（`http://<IP>:8088`）、UUID 和密码，点击测试连接

4. 开启自动同步（建议间隔 5-30 分钟），之后每次浏览器登录 PT 站，Cookie 自动加密上传

5. skill 的 `cookie_sync.py` 拉取解密后写入 `secrets.env`，keepalive 检测 cookie 失效时自动触发同步
