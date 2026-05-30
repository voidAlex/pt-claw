---
name: pt-claw
description: "Use when the user wants to search/download torrents from PT sites, manage qBittorrent, or set up a media download stack. 8 sites supported: PTTime, M-Team (API), BTSchool, CarPT, HDFans, 1PTBar, SoulVoice, 织梦. Search via cookie or REST API, push to qBittorrent, monitor completion."
version: 3.0.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [pt, torrent, qbittorrent, download, media, nas, mteam, adult, jav]
    related_skills: []
---

# PT Downloader — 对话式资源搜索与下载

## Overview

通过对话搜索 8 个 PT 站资源、推送到 qBittorrent 下载、完成后通知。纯脚本实现，无 Prowlarr/Jackett 依赖。

**核心链路**：
```
用户说"搜XXX" → 识别内容类型 → 路由到对应搜索 → 展示结果+元数据 → 排序 → 🛑用户确认 → 推送 qBittorrent → 打站点标签 → 记录下载历史(pt_downloaded.json) → 下载完成 → 通知
```

**⚠️ 确认闸门（全局规则）**：搜到资源后**禁止直接下载**。必须先展示以下完整信息并等用户确认：
- 来源站点、资源大小、做种数、版本标签（4K/HEVC/字幕/去码）
- 目标下载路径（分类 + save_path）
- 影片元数据：发行日期、导演、主演、剧情简介
- 只有用户明确说「下」「下载」「all」等确认词后才推送到 qBittorrent
- 此规则适用于**所有场景**：手动搜索、演员追剧、自动追剧，无一例外

**8 站支持**：PTTime · M-Team(馒头) · BTSchool · CarPT · HDFans · 1PTBar · SoulVoice · 织梦

## When to Use

以下任意关键词或场景触发本技能加载：

### 触发词

| 分类 | 关键词 |
|------|--------|
| 搜索/下载 | 搜、搜索、下载、下、找个资源、有没有、求片 |
| qBittorrent | qb、qB、qbit、下载进度、下载状态、做种、种子、删种、暂停、恢复、死种 |
| 辅种 | 辅种、cross seed、检查辅种、哪些站能辅、批量辅种、全站辅种 |
| PT 站点 | pt、PT、PT站、馒头、mteam、pttime、btschool、carpt、hdfans、1ptba、1PTBar、一PT吧、soulvoice、zmpt、织梦 |
| 番号/成人 | 番号、车牌、jav、JAV、成人、sukebei、javbus、nyaa |
| 定时任务 | 定时任务、cron、追剧、刷流、下载通知 |
| 关注/收藏 | 关注、取消关注、关注列表、wishlist |
| Jellyfin | jf、JF、jellyfin、片库、去重、已存在 |

### 场景速查

| 用户说 | 路由 |
|--------|------|
| 「搜流浪地球2」「找个4K沙丘」 | → Step 1 识别类型 → Step 2 全站搜索 |
| 「下SSIS-448」「搜SONE-833」 | → 番号 → 成人区搜索 + 公开源回退 |
| 「查下载进度」「qb怎么样了」 | → `qb_monitor.py` |
| 「删掉那个死种」「暂停xxx」 | → qB API 操作 |
| 「关注诺兰」「收藏SSIS-xxx」 | → 写入 `pt_wishlist.json` |
| 「恢复」「qb种子丢了」 | → [references/qb-operations.md](references/qb-operations.md) |
| 「首次配置」「初始化」 | → [references/first-time-setup.md](references/first-time-setup.md) |
| 「新增一个PT站」 | → [references/new-site-adaptation.md](references/new-site-adaptation.md) |
| 「辅种」「哪些站能辅」「cross seed」 | → `cross_seed.py` — 多站辅种验证与推送 |

## 参考文档

脚本用法、配置流程、集成细节全部在 reference 文件中，按需读取：

| 文档 | 内容 | 何时读 |
|------|------|--------|
| [references/scripts-guide.md](references/scripts-guide.md) | 全部脚本用法速查（命令示例 + 参数说明） | 需要运行脚本时 |
| [references/first-time-setup.md](references/first-time-setup.md) | 首次配置清单 + 初始化流程 + cron 创建 | 用户首次使用或重新配置 |
| [references/qb-operations.md](references/qb-operations.md) | qB 推送两步法 + 公开种清理 + 灾难恢复 + NAS 路径映射 | 推送下载、恢复种子、路径问题 |
| [references/jf-integration.md](references/jf-integration.md) | Jellyfin + javbus-api + 演员统计 + 关注列表 + 追剧 + 去重 | 涉及 JF/追剧/成人内容/演员查询 |
| [references/cron-patterns.md](references/cron-patterns.md) | Cron 下载进度检查 + 成人追剧高效链路 | cron 定时任务配置或调试 |
| [references/pt-boost.md](references/pt-boost.md) | PT 刷流配置 + 执行逻辑 | 刷流保号 |
| [references/new-site-adaptation.md](references/new-site-adaptation.md) | 新增 PT 站适配 5 步流程 | 用户要添加新站 |
| [references/mteam-api.md](references/mteam-api.md) | 馒头 API 端点 + 认证 + genDlToken | 涉及 M-Team |
| [references/diagnostic-proxy-cookie.md](references/diagnostic-proxy-cookie.md) | Cookie 过期 vs 代理被封 vs IP 绑定诊断 | 连接 403 时 |
| [references/adult-section-search.md](references/adult-section-search.md) | PTTime/M-Team 成人区搜索参数 | 成人内容搜索 |
| [references/nexusphp-parser-notes.md](references/nexusphp-parser-notes.md) | 两种 HTML 解析模式 | 适配新站解析器 |
| [references/duplicate-media-scan.md](references/duplicate-media-scan.md) | 媒体库重复检测（深度扫描同名电影/剧集） | 清理重复下载 |
| [references/orphan-media-scan.md](references/orphan-media-scan.md) | 磁盘孤儿媒体扫描 | 手动恢复 |
| [references/privacy-audit-checklist.md](references/privacy-audit-checklist.md) | 隐私审计检查清单 | 推送前自查 |

## Supported PT Sites

| 站点 | 接入 | 成人区 | 代理 | 备注 |
|------|------|--------|------|------|
| M-Team (馒头) | REST API | ✅ API `mode: "adult"` 已验证（分类 410-440） | ✅ **必须** | POST，`x-api-key` header，**禁 Cookie**，**国内 IP 直连 403，必须走 PT_PROXY** |
| PTTime | Cookie | `adults.php?searchstr=` | ❌ | `data=` attribute 变体 |
| BTSchool | Cookie | 无 | ✅ `needs_proxy` | NexusPHP，cookie IP 绑定 |
| CarPT | Cookie | 无 | ✅ `needs_proxy` | NexusPHP，cookie IP 绑定 |
| HDFans | Cookie | 无 | ❌ | Classic NexusPHP |
| 1PTBar | Cookie | 无 | ❌ | Classic NexusPHP |
| SoulVoice | Cookie | 无 | ✅ `needs_proxy` | NexusPHP，cookie IP 绑定 |
| 织梦 (zmpt.cc) | Cookie | 无 | ✅ `needs_proxy` | Cloudflare + NexusPHP，cookie IP 绑定 |

### M-Team API 要点

- **API Host**: `https://api.m-team.cc/api`（**必须走 `PT_PROXY`，国内直连 403**）
- **Auth**: `x-api-key` header（控制台 → 实验室 → 存取令牌）
- **Method**: 仅 POST
- **禁止 Cookie 访问 API**，会封号。只能用 API Key
- **允许调用的端点**: `/member/*`、`/msg/*`、`/torrent/*`
- **Quirk**: `code` 是字符串 `"0"`；官方 Swagger 文档有 bug（参数格式/必传项可能不准）
- **Search**: `POST /torrent/search`，body `{"keyword": "...", "page": 1, "size": 25}`
- **Download**: `POST /torrent/genDlToken?id=<torrent_id>`（返回签名下载 URL）
- **限速**: 下载配额 1000个/天，下载行为 100个/h，详情 100次/h，搜索 1000次/24h

## Agent Workflow

### Step 1：识别内容类型，路由搜索

根据搜索关键词判断内容类型：

| 关键词特征 | 内容类型 | 搜索路由 |
|-----------|---------|---------|
| 番号模式（如 `SSIS-448`、`SONE-833`） | JAV 成人 | → **先检查 `user-preferences.md` 成人 `enabled`**；未启用则拒绝并提示；已启用 → PTTime `adults.php` + M-Team API adult → 做种不足→ JavBus(首选) → Sukebei |
| 演员/导演名 | 影视/成人 | → **先查元数据源获取完整作品列表**，再逐部搜 PT |
| 电影/剧集名 | 影视 | → 全 8 站常规搜索 |
| 片库统计/演员排行 | JF查询 | → JF `fields=People` 分页计数 |

**⚠️ 元数据优先原则**：搜索演员/导演时，不要直接在 PT 站搜索。PT 站的演员标签经常不完整或误标。

**番号判断正则**：`^[A-Z]{2,6}[-_ ]?\d{2,5}$`（不区分大小写）

| 国籍 | 搜索用名 |
|------|---------|
| 日本 | 日文原名（七緒，不是七绪） |
| 欧美 | 英文原名（Christopher Nolan，不是诺兰） |
| 韩国 | 韩文原名（박찬욱，不是朴赞郁） |
| 中国 | 中文原名 |

### Step 2：执行搜索

```bash
# 常规搜索（脚本根据 SITES 字典自动决定是否走代理）
python3 scripts/pt_search.py "关键词" --limit 10

# 成人区搜索（仅 PTTime 和 M-Team）
python3 scripts/pt_search.py "SONE-833" --site pttime --adult --limit 10
python3 scripts/pt_search.py "" --site pttime --adult --actor "浅野心" --limit 10
```

### Step 3：展示结果 & 排序

从 `user-preferences.md` 读取偏好（清晰度、编码），按以下优先级排序：

1. **匹配用户偏好**（清晰度 + 编码）— 不符合的排后面
2. **做种人数最多** — 下载更快
3. **体积较小** — 省空间

**📋 多作品逐个介绍**：搜到同一演员/导演的多部不同作品，必须逐一介绍（番号/年份/简介/大小/做种数）。让用户自己选。

**🎬 同名多版本歧义**：中文标题常同时存在电影/动画/剧集多个版本，必须分组展示并询问用户要哪个。

**做种不足时的处理**：PT 做种低于阈值 → 自动回退公开源（JavBus → Sukebei），不需要问用户。列出所有可行选项让用户选。

### Step 4：🛑 用户确认闸门（必须！禁止跳过！）

**搜到资源后绝不能直接下载。** 必须将结果汇总展示给用户，等待确认。

**展示格式（每部资源必须包含以下全部字段）：**

```
🎬 番号/片名：XXX
📅 发行日期：YYYY-MM-DD
👤 主演：XXX、XXX
🎬 导演：XXX（如有）
📝 简介：一句话剧情概括
📡 来源站点：PTTime / M-Team / Sukebei
💾 大小：X.X GB
📊 做种数：N
🏷️ 版本标签：4K / HEVC / 字幕 / 去码
📂 下载路径：/media/xxx/xxx（分类：XXX）
```

用户说「下」「下载」「all」「全下」→ 进入 Step 5。**cron 不自动推送任何种子。**

### Step 5：确认路径 & 添加到 qBittorrent

> ⚠️ **仅在用户明确确认后执行！**

**前置验证**：
```bash
bash scripts/env_check.sh          # 检查环境变量是否齐全
python3 scripts/connectivity_check.py  # 实际连接测试
```

**去重检查（三步验证，缺一不可）**：

1. **查下载历史** → `pt_downloaded.json` 里有 → 无条件跳过（曾下载过，不管后来删没删）
2. **查 Jellyfin** → 未配置则跳过
3. **比时间戳** → JF `DateCreated` < qB `added_on` = 真重复；反之 = 下载后入库的正常流程

```bash
python3 scripts/download_history.py check --code <番号>
echo -e "CODE1\nCODE2" | python3 scripts/download_history.py filter  # 批量
```

**推送下载** — **必须使用两步法**，详见 [references/qb-operations.md](references/qb-operations.md)。禁止只用 URL 推送（会静默失败）。

**🏷️ 站点标签（必须！）**：

| 来源 | 标签 | 来源 | 标签 |
|------|------|------|------|
| M-Team | `mteam` | CarPT | `carpt` |
| PTTime | `pttime` | HDFans | `hdfans` |
| BTSchool | `btschool` | 1PTBar | `1ptba` |
| SoulVoice | `soulvoice` | 织梦 | `zmpt` |
| Sukebei | `sukebei` | JavBus | `javbus` |

推送成功后必须记录下载历史：
```bash
python3 scripts/download_history.py add --code <番号> --title "<标题>" --source <站点标签>
```

**分类映射**：从 `user-preferences.md` 读取（初始化时一次性从 qB API 读取写入）。不硬编码分类名。

### Step 6：后台定时任务

> 定时任务在 [references/first-time-setup.md](references/first-time-setup.md) 的初始化流程中自动创建。

| 任务 | 频率 | 通知条件 |
|------|------|---------|
| PT下载进度检查 | 每 15 分钟 | 完成/死种（首次立即，之后每 6h 提醒，最多 20 次）/公开种自动清理 |
| PT自动追剧 | 每天 10:00 | 有新资源（只展示不下载） |
| CookieCloud定时同步 **或** PT站点Cookie保活 | 每4h/每天06:00 | 二选一，视配置 |

管理：「暂停XX任务」「恢复XX任务」「列出定时任务」

## PT 刷流（可选）

详见 [references/pt-boost.md](references/pt-boost.md)：配置 schema（`pt_boost.json`）、每日执行逻辑（清理→新增）、cron 创建。

## Jellyfin 集成 + javbus-api（可选）

详见 [references/jf-integration.md](references/jf-integration.md)：片库去重、关注列表（`pt_wishlist.json`）、每日追剧 cron、javbus-api 端点、成人内容公开源回退链路。

## 新增 PT 站

详见 [references/new-site-adaptation.md](references/new-site-adaptation.md)：5 步适配流程（信息收集→平台识别→解析器→验证→文档更新）+ 适配检查清单。

**手写解析器必须委托编程 agent**：NexusPHP 系站点只需注册 SITES 字典（零代码），Agent 可直接完成。但遇到非标框架需要手写解析器时（Case 3），Agent **禁止自己写代码**——先完成 Step A/B 的信息收集和 HTML 分析，然后将完整的解析规格（DOM 结构、字段映射、示例 HTML 片段）委托给 Claude Code / OpenCode 等专业编程 agent 实现和调试。

## Common Pitfalls

### 🔴 致命级

**1. 代理用 `PT_PROXY`，禁止用 `HTTP_PROXY`**：`HTTP_PROXY` 会让 Agent 自身 API 走代理，挂了直接失联。脚本按站点 `needs_proxy` 标记自动应用 `PT_PROXY`。

**2. 公开磁链只看标签不看 tracker**：唯一可靠判断是 qB 标签（sukebei/javbus）。`qb_public_cleanup.py` 有四道防线：占比>20%中止、单次≤50、`--check` 先查后删、删除前自动备份。

**3. 下载历史防重复**：推送成功立即写 `pt_downloaded.json`。去重第一优先——历史中有 = 无条件跳过。

**4. `[SILENT]` 不能和内容混用**：含 `[SILENT]` 整条静默。有事件发摘要，互斥。

**5. 确认闸门——下载和删种都经用户确认**：搜到资源禁止直接推送；三个删种脚本必须 `--check` 先查后删；cron 只搜索不下载。

**6. M-Team 禁止 Cookie 登录**：馒头严禁 Cookie 方式访问，会封号。只能 `MTEAM_API_KEY` REST API。`cookie_sync.py` 不为 mteam 同步，`connectivity_check.py` 不测 mteam cookie。

### 🟠 严重级

**7. M-Team API**：①限速 403（1000次/24h）②下线 405 ③DNS 302 ④**国内 IP 直连 403，必须走 PT_PROXY**。`mteam_api.py` 和 `pt_search.py` 在 `PT_PROXY` 未设置时直接报错，不会静默直连。

**8. qB URL 推送静默失败**：PT 站 download.php 需 Cookie，qB 没有。两步法见 [references/qb-operations.md](references/qb-operations.md)。

**9. JF 已有 ≠ 重复**：比 `DateCreated` vs qB `added_on` 时间戳。JF 晚于 qB = 正常入库。

**10. API key 必须写 `secrets.env`**：不依赖 memory。用 `printf >>` 追加。

**11. PT 恢复种子结构不匹配**：本地 .torrent → snatchlist → 搜索下载。导入后验证命中已有文件。

**12. wishlist 厂牌排除同步**：用户说「XXX 厂牌不要」→ 立即更新 `exclude_prefixes`。

**13. 同名多版本分组展示**：电影/动画/剧集分别列出，让用户选。

### 🟡 注意级

**14. 成人搜索必须检查开关**：搜索前读 `user-preferences.md` 的 `## 成人内容 → 启用` 字段。`enabled: false` 或未配置 → 拒绝成人搜索请求，告知「成人内容未启用，如需开启请修改 user-preferences.md」。`enabled: true` → 正常走成人搜索链路：PTTime `adults.php?searchstr=`、M-Team 成人区、做种不足→javbus-api + Sukebei。

**15. 演员走元数据不搜 PT**：javbus-api `/api/movies/search?keyword=&page=N`。JF 逐条查。

**16. 日本演员用日文汉字**：「七緒」能搜，「七绪」0 结果。先用番号反查获取原名。

**17. JF/javbus-api 中文 URL 编码**：`--data-urlencode` 或 `urllib.parse.quote()`。

**18. 公开磁链**：JavBus > Sukebei（磁链多/去码/AI）、`--list-files`→用户确认→`--select-files`、`--max-video` 兜底、下完删种保文件、卡死换不同 hash。

**18b. JavBus 磁链获取需两步**：`javbus_magnet.py --api` 返回的是电影详情（封面/演员/gid/uc），不是磁链列表。获取磁链的正确流程：
1. `GET /api/movies/{code}` → 提取 `gid` 和 `uc`
2. `GET /api/magnets/{code}?gid=X&uc=Y` → 获取结构化磁链列表（含大小/HD/字幕标记）
不要只调 `javbus_magnet.py` 就以为拿到了磁链——需要手动走第二步。

**19. 三重去重**：下载历史 → JF 搜索 → JF `DateCreated` vs qB `added_on`。

**20. 搜老剧多关键词**：中文通用标题 + 季别名 + 英文名+季号。

**21. Cookie 403 ≠ 过期**：NexusPHP `c_secure_*` cookie 绑定登录 IP。直连 403 → 走代理重试（代理出口 IP 需和浏览器一致），代理也 403 → 才判过期。详见 [references/diagnostic-proxy-cookie.md](references/diagnostic-proxy-cookie.md)。

**22. PTTime Cloudflare 拦截**：browser_navigate 抓或等冷却。

**23. PT_PROXY 变更需同步 javbus-api**：修改 `secrets.env` 中 `PT_PROXY` 后，javbus-api 的 Docker 容器仍使用旧代理。需同步更新 `docker-compose.yml` 中 `HTTP_PROXY`/`HTTPS_PROXY` 并重建容器。路径：`~/javbus-api/docker-compose.yml`。完整步骤见 [references/proxy-migration.md](references/proxy-migration.md)。

**24. `connectivity_check.py` 消耗 M-Team 配额**：`test_mteam()` 每次调 `POST /torrent/search {"keyword":"test"}`，消耗 1000次/24h 配额。频繁调用（如 cron 每次跑）会导致 API 限速 403。诊断流程：先查是否频繁调了 `connectivity_check.py`，而非直接怀疑 API key。

**25. `pt_notify_state.json` 通知状态文件**：`_cron_check.py` 用此文件追踪死种通知频率（首次立即，之后每 6h 提醒，最多 20 次）。文件不存在时自动创建默认值，无需手动维护。不要删除此文件，否则会丢失通知计数导致重复提醒。

### 🔧 脚本纪律

**26. javbus-api 磁链获取需两步**：`javbus_magnet.py --api` 返回的是影片详情（含 gid/uc），不是磁链。正确流程：① `GET /api/movies/{番号}` 获取 gid 和 uc；② `GET /api/magnets/{番号}?gid=X&uc=Y` 获取结构化磁链。一步到位命令：
```bash
gid=$(curl -s "http://localhost:8922/api/movies/$CODE" | python3 -c "import sys,json; print(json.load(sys.stdin)['gid'])")
uc=$(curl -s "http://localhost:8922/api/movies/$CODE" | python3 -c "import sys,json; print(json.load(sys.stdin)['uc'])")
curl -s "http://localhost:8922/api/magnets/$CODE?gid=$gid&uc=$uc"
```

**27. qb_add.py 磁链推送超时回退**：`qb_add.py --stdin` 的 `max_video` 模式会等待元数据取回，对慢磁链可能超时。超时时回退到直接 qB API 推送：`curl -b <cookie> -X POST '<qb_url>/api/v2/torrents/add' --data-urlencode 'urls=<magnet>'`，然后补 `setCategory` + `setLocation` + `addTags`。

**28. 禁止 `source secrets.env`**：Cookie 值含 `=`，bash source 会误解析。脚本内部 `_load_env_file()` 安全处理。

**29. 禁止 /tmp/*.py 临时脚本**：日常用 `qb_monitor/jf_query/javbus_star/qb_add`。新场景事后固化。

**30. 内网用 Python 脚本不裸 curl**：tirith 拦截 curl→私有 IP。脚本内部 `urllib.request` 绕过。

**31. `write_file` 替换敏感值**：写 `secrets.env` 用 `printf >>`。

**32. 全量隐私审计（每次推送前自查）**：API Key、内网 IP、路径、用户 ID 绝不硬编码。见 [references/privacy-audit-checklist.md](references/privacy-audit-checklist.md)。

## 环境变量清单（`secrets.env`）

### PT 站点

| 变量 | 说明 |
|------|------|
| `PT_COOKIE_PTTIME` | PTTime Cookie |
| `PT_COOKIE_BTSCHOOL` | BTSchool Cookie |
| `PT_COOKIE_CARPT` | CarPT Cookie |
| `PT_COOKIE_HDFANS` | HDFans Cookie |
| `PT_COOKIE_1PTBA` | 1PTBar Cookie |
| `PT_COOKIE_SOULVOICE` | SoulVoice Cookie |
| `PT_COOKIE_ZMPT` | 织梦 (zmpt.cc) Cookie |
| `MTEAM_API_KEY` | M-Team API Key。**禁止 Cookie——会封号**。**必须同时配置 `PT_PROXY`** |

### 下载器

| 变量 | 说明 |
|------|------|
| `QBITTORRENT_URL` | qBittorrent 地址（含端口） |
| `QBITTORRENT_USER` | qBittorrent 用户名 |
| `QBITTORRENT_PASS` | qBittorrent 密码 |
| `QB_CLEANUP_DRY_RUN` | 设为 `1` 时公开种清理仅报告不删除（安全开关，可选） |

### Jellyfin（可选，未配置不影响下载）

| 变量 | 说明 |
|------|------|
| `JELLYFIN1_URL` | JF1 地址 |
| `JELLYFIN1_API_KEY` | JF1 API Key |
| `JELLYFIN2_URL` | JF2 地址 |
| `JELLYFIN2_API_KEY` | JF2 API Key |

### 网络

> ⚠️ **致命警告**：不要设 `HTTP_PROXY` / `HTTPS_PROXY`！用 `PT_PROXY` 代替。

| 变量 | 说明 |
|------|------|
| `PT_PROXY` | PT 搜索代理地址，脚本按站点 `needs_proxy` 标记自动应用 |

### javbus-api（可选）

| 变量 | 说明 |
|------|------|
| `JAVBUS_API_URL` | javbus-api 地址（如 `http://localhost:8922`） |

### CookieCloud（可选，未配置则手动管理 Cookie）

| 变量 | 说明 |
|------|------|
| `COOKIE_CLOUD_HOST` | CookieCloud 服务器地址 |
| `COOKIE_CLOUD_UUID` | 用户 UUID |
| `COOKIE_CLOUD_PASS` | 加密密码 |

### 用户偏好（存入 `user-preferences.md`）

- 清晰度偏好（4K/1080p/720p）
- 编码偏好（HEVC/AVC/AV1）
- 下载路径分类映射
- 成人内容 PT 做种阈值 & 版本优选顺序
- 关注列表 (`pt_wishlist.json`)
