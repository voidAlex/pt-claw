# First-Time Setup — 首次配置流程

## Agent Workflow

### Step 0：初次使用 — 主动询问用户配置

**当用户第一次使用 PT 下载功能时（没有本地 `user-preferences.md` 文件），必须主动询问以下信息：**

**配置模板**：`templates/user-preferences.example.md` 包含所有配置维度和占位符。首次配置时读取此模板作为参考，逐项向用户确认，用真实值填充后写入本地 `user-preferences.md`（不入 Git）。敏感值（API key、密码、IP）写入 `secrets.env`。**不写入 memory**（memory 容量有限，偏好配置数据量大，全部走文件）。

询问清单：

1. **PT 站点**：有哪些站？目前支持 8 站（M-Team、PTTime、BTSchool、CarPT、HDFans、1PTBar、SoulVoice、织梦），不在列表中的需要新增适配。
2. **下载器**：类型、地址、端口、用户名、密码（目前支持 qBittorrent）。
3. **下载路径偏好**：读取 qBittorrent 分类 API，展示所有分类和路径，让用户确认内容类型映射（电影/电视剧/成人等 → 分类 → 路径），写入 `user-preferences.md`。
4. **清晰度偏好**：2160p / 1080p / 720p / 无偏好。
5. **编码格式偏好**：HEVC / AVC / AV1 / 无偏好。
6. **其他偏好**（可选）：原盘 vs 压制、字幕、音轨、制作组。
7. **通知偏好**：下载完成后通知到哪里？
8. **代理配置**：代理地址、哪些站需要代理。
9. **Jellyfin 集成（可选）**：是否有 Jellyfin 服务器？几个？分别什么用途（影视/成人/音乐）？地址和 API Key？→ 没配置也能正常下载，只是无法自动去重。**API key 写入 `secrets.env`**，跨会话不丢失。
10. **javbus-api（可选）**：是否已部署 javbus-api（`docker compose` 模板在 `templates/docker-compose.javbus-api.yml`）？→ 已部署则在 `secrets.env` 设置 `JAVBUS_API_URL=http://localhost:8922`。未部署也能裸爬 JavBus，只是磁链无结构化数据、无封面预览。
11. **PT 刷流（可选）**：是否需要自动刷流保号？→ 需要指定：站点、搜索条件（关键词/免费/HR排除）、大小范围、做种人数、qB 专用目录、做种天数上限、死种清理阈值、每次新增上限。配置写入 `<skill-dir>/pt_boost.json`。
12. **成人内容下载偏好（可选）**：PT 做种阈值（低于N则走公开源）、版本优选顺序（做种数/去码/字幕/画质）、清晰度范围（4K/1080p/720p）。
13. **CookieCloud（可选）**：是否已部署 CookieCloud？→ 已部署则提供服务器地址、UUID、密码，写入 `secrets.env`（`COOKIE_CLOUD_HOST/UUID/PASS`）。未部署则提供 Docker Compose 模板（`templates/docker-compose.cookiecloud.yml`）引导部署，并提示安装浏览器扩展。CookieCloud 可自动同步浏览器 Cookie 到 skill，免去手动抓 cookie 的麻烦。需要系统安装 `python3-cryptography`。

所有回答写入 `user-preferences.md`（本地文件，不入 Git）。敏感值同时写入 `secrets.env`。不使用 memory 存储偏好（容量有限）。

#### 配置完成后自动初始化

用户回答完以上问题后，**不要等用户说，直接自动执行以下初始化**：

**1. 安装依赖（如果缺失）：**

```bash
# cookie_sync.py 解密依赖
dpkg -l python3-cryptography >/dev/null 2>&1 || sudo apt-get install -y python3-cryptography
```

**2. 创建数据文件：**

```bash
# 下载历史（不存在则创建，schema 见 templates/pt_downloaded.example.json）
test -f pt_downloaded.json || echo '{"description":"下载历史 — 防止用户手动删除后定时任务重复下载","items":[]}' > pt_downloaded.json

# 完成通知跟踪（不存在则创建）
test -f pt_completed_last.txt || touch pt_completed_last.txt

# 关注列表（不存在则创建，schema 见 templates/pt_wishlist.example.json）
test -f pt_wishlist.json || echo '{"movies":[],"actors":[],"fanhao":[]}' > pt_wishlist.json
```

**3. 首次 Cookie 同步（如果配置了 CookieCloud）：**

```bash
python3 scripts/cookie_sync.py
python3 scripts/connectivity_check.py --quick
```

如果用户未配置 CookieCloud，跳过此步。`secrets.env` 中的 `PT_COOKIE_*` 需要用户手动从浏览器抓取填入。

**4. 创建定时任务（必须，不等用户追问）：**

| 任务 | 频率 | 作用 |
|------|------|------|
| PT下载进度检查 | 每 15 分钟 | 完成通知 + 死种告警，没事件时不发消息 |
| PT自动追剧 | 每天 10:00 | 搜索+去重+展示，等用户确认后才下载 |
| 公开磁链状态检查 | 每 30 分钟 | 自动删除已完成公开种、标记死种 |
| CookieCloud定时同步 | 每 4 小时 | 从 CookieCloud 拉取最新 cookie 更新 secrets.env（配置了 CookieCloud 时） |
| PT站点Cookie保活 | 每天 06:00 | 访问各站首页刷新 session（未配置 CookieCloud 时才创建） |

```python
# 下载进度检查（静默模式：没事件不通知）
cronjob(action='create',
    name="PT下载进度检查",
    schedule="every 15m",
    repeat="forever",
    prompt="""加载 pt-claw skill，检查 qBittorrent 下载进度。skill 目录下已有 secrets.env（凭据）、user-preferences.md（偏好）、pt_completed_last.txt（上次检查时间戳）。

只做三件事：
1. 有下载完成的（progress=100%）→ 通知「✅ xxx 下载完成」，更新 pt_completed_last.txt
   - 公开磁链（sukebei/javbus 标签）完成后自动调 qb_public_cleanup.py 停止做种保留文件
2. 超7天0%死种 → 通知「💀 xxx 已死种N天，回复「删」清理」
   - ⚠️ 不要自动删除，等用户确认
3. 都没有 → 整个回复仅：[SILENT]

脚本内部通过 `_load_env_file()` 自动读取 secrets.env，无需手动 source。""",
    skills=["pt-claw"],
    deliver="origin",
    workdir="<skill-dir>",
)

# 自动追剧（只搜索展示，不自动下载）
cronjob(action='create',
    name="PT自动追剧",
    schedule="0 10 * * *",
    prompt="""加载 pt-claw skill，自动追剧检查（只搜索展示，不自动下载）。skill 目录下已有 secrets.env、user-preferences.md、pt_wishlist.json、pt_downloaded.json。

1. 读 pt_wishlist.json + pt_downloaded.json
2. 搜资源 → 三重去重（历史>JF>时间戳）
3. 检查 exclude_prefixes 排除封禁厂牌
4. 展示结果：每部列出站点、大小、做种数、下载路径、元数据（日期/导演/主演/简介）
5. **绝对不推送下载**——等用户说「下」确认
6. 无新资源则「今日无新资源」

脚本内部通过 `_load_env_file()` 自动读取 secrets.env，无需手动 source。""",
    skills=["pt-claw"],
    deliver="origin",
    workdir="<skill-dir>",
)

# 公开磁链清理（只报告不自动删）
cronjob(action='create',
    name="公开磁链状态检查",
    schedule="every 30m",
    repeat="forever",
    prompt="""加载 pt-claw skill。运行 `python3 scripts/qb_public_cleanup.py --check` 检查公开磁链（TAG ONLY：sukebei/javbus，禁止 tracker URL 匹配）。
- 无事 → [SILENT]
- 有事 → 列出待清理清单，结尾「回复「清了」确认删除」
⚠️ 绝对不能自动删种，必须等用户确认""",
    skills=["pt-claw"],
    deliver="origin",
    workdir="<skill-dir>",
)

# CookieCloud 定时同步（仅当配置了 CookieCloud 时创建）
# 如果 secrets.env 中没有 COOKIE_CLOUD_HOST 则跳过此任务
# 配置了 CookieCloud 后不需要 keepalive——CookieCloud 定时同步已覆盖 cookie 刷新需求
cronjob(action='create',
    name="CookieCloud定时同步",
    schedule="0 */4 * * *",
    prompt="""加载 pt-claw skill。检查 secrets.env 中是否有 COOKIE_CLOUD_HOST 配置。
如果有，运行 `python3 scripts/cookie_sync.py` 同步 cookie，然后 `python3 scripts/connectivity_check.py --quick` 验证。
如果 CookieCloud 未配置则 [SILENT] 跳过。
同步失败或连接异常时报告用户。""",
    skills=["pt-claw"],
    deliver="origin",
    workdir="<skill-dir>",
)

# Cookie 保活（仅当未配置 CookieCloud 时创建）
# 如果 secrets.env 中有 COOKIE_CLOUD_HOST 则跳过——CookieCloud 同步已覆盖
cronjob(action='create',
    name="PT站点Cookie保活",
    schedule="0 6 * * *",
    prompt="""加载 pt-claw skill。检查 secrets.env 中是否有 COOKIE_CLOUD_HOST 配置。
如果有则 [SILENT] 跳过（CookieCloud 已覆盖 cookie 刷新）。
如果没有，运行 `python3 scripts/connectivity_check.py --keepalive`，只报告失败的站点。全部成功则 [SILENT]。
脚本内部通过 `_load_env_file()` 自动读取 secrets.env，无需手动 source。""",
    skills=["pt-claw"],
    deliver="origin",
    workdir="<skill-dir>",
)
```

> ⚠️ 定时任务创建后告知用户：「已创建 4 个定时任务——下载进度(15m)、自动追剧(10:00)、公开种检查(30m)、CookieCloud同步或Cookie保活(视配置而定)。随时可以说『暂停XX任务』来停止。」
> CookieCloud 同步和 Cookie 保活互斥：配置了 `COOKIE_CLOUD_HOST` 则只创建同步任务（每4h），未配置则只创建保活任务（每天06:00）。Agent 创建时应检查 `secrets.env` 中是否有 `COOKIE_CLOUD_HOST` 来决定创建哪个。实际同时运行的定时任务始终为 4 个。
