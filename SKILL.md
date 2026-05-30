---
name: pt-claw
description: "PT种子搜索下载与qBittorrent管理技能。搜索/下载/辅种/刷流/站点管理时触发——包括搜片、下片、qb管理、查做种、删种、辅种、查站内信息、刷流保号、Cookie同步、追剧等场景。15站支持，纯脚本无外部依赖。"
version: 3.0.2
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [pt, torrent, qbittorrent, download, media, nas, mteam, adult, jav, 辅种, 刷流]
    related_skills: []
---

# pt-claw — PT 多站搜索下载与 qBittorrent 管理

## Overview

通过对话搜索 15 个 PT 站资源、推送到 qBittorrent 下载、完成后通知。纯脚本实现，无 Prowlarr/Jackett 依赖。

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

**15 站支持**：PTTime · M-Team(馒头) · BTSchool · CarPT · HDFans · 1PTBar · SoulVoice · 织梦 · PTSkit · PTHome · HDSky · HDHome · Audiences(观众) · KeepFriends(朋友) · ToTheGlory(TTG)

## When to Use

以下任意关键词或场景触发本技能加载：

### 触发词

| 分类 | 关键词 |
|------|--------|
| 搜索/下载 | 搜、搜索、下载、下、找个资源、有没有、求片 |
| qBittorrent | qb、qB、qbit、下载进度、下载状态、做种、种子、删种、暂停、恢复、死种 |
| 辅种 | 辅种、cross seed、检查辅种、哪些站能辅、批量辅种、全站辅种 |
| PT 站点 | pt、PT、PT站、馒头、mteam、pttime、btschool、carpt、hdfans、1ptba、1PTBar、一PT吧、soulvoice、zmpt、织梦、ptskit、拾刻、pthome、铂金家、hdsky、天雪、hdhome、家园、audiences、观众、keepfrds、朋友、ttg、套套哥、听听歌、totheglory |
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

## 脚本清单

所有脚本用法、参数说明和命令示例见 [references/scripts-guide.md](references/scripts-guide.md)。

| 脚本 | 用途 |
|------|------|
| `pt_search.py` | 多站搜索（15 站 NexusPHP + M-Team API） |
| `qb_add.py` | 添加种子到 qBittorrent |
| `qb_monitor.py` | qB 状态/过滤/删除/死种诊断 |
| `cross_seed.py` | 多站辅种验证与推送 |
| `site_profile.py` | 多站用户信息查询 |
| `pt_ratio_boost.py` | Freeleech 刷流保号 |
| `qb_snapshot.py` | 删种备份与恢复 |
| `qb_public_cleanup.py` | 公开磁链清理 |
| `_cron_check.py` | Cron 综合检查（完成/死种/清理） |
| `connectivity_check.py` | 全服务连接测试 |
| `cookie_sync.py` | CookieCloud 同步 |
| `download_history.py` | 下载历史防重复 |
| `mteam_api.py` | M-Team API 客户端 |
| `sukebei_search.py` | Sukebei RSS 搜索 |
| `javbus_magnet.py` | JavBus 磁链爬取 |
| `javbus_star.py` | 演员片单交叉对比 |
| `jf_query.py` | Jellyfin 查询 |
| `env_check.sh` | 环境变量检查 |

## 参考文档

脚本用法、配置流程、集成细节全部在 reference 文件中，按需读取：

| 文档 | 内容 | 何时读 |
|------|------|--------|
| [references/scripts-guide.md](references/scripts-guide.md) | 全部脚本用法速查（命令示例 + 参数说明） | 需要运行脚本时 |
| [references/first-time-setup.md](references/first-time-setup.md) | 首次配置清单 + 初始化流程 + cron 创建 | 用户首次使用或重新配置 |
| [references/qb-operations.md](references/qb-operations.md) | qB 推送两步法 + 公开种清理 + 灾难恢复 + NAS 路径映射 | 推送下载、恢复种子、路径问题 |
| [references/jf-integration.md](references/jf-integration.md) | Jellyfin 连接配置 + 去重 + 追剧 + 关注列表 | 涉及 JF/追剧/去重 |
| [references/cron-progress-check.md](references/cron-progress-check.md) | Cron 进度检查 + 公开种清理 + 死种告警 | cron 进度监控配置或调试 |
| [references/adult-content.md](references/adult-content.md) | javbus-api + 成人区搜索 + 公开磁链 + 成人追剧链路 | 成人内容搜索/追剧/磁链 |
| [references/pt-boost.md](references/pt-boost.md) | PT 刷流配置 + 执行逻辑 | 刷流保号 |
| [references/new-site-adaptation.md](references/new-site-adaptation.md) | 新增 PT 站适配 5 步流程 | 用户要添加新站 |
| [references/mteam-api.md](references/mteam-api.md) | 馒头 API 端点 + 认证 + genDlToken | 涉及 M-Team |
| [references/diagnostic-network.md](references/diagnostic-network.md) | Cookie/代理/IP绑定诊断 + 代理变更检查清单 | 连接 403 或代理迁移时 |
| [references/media-maintenance.md](references/media-maintenance.md) | 媒体库重复检测 + 磁盘孤儿扫描 | 清理重复下载或手动恢复 |
| [references/privacy-audit-checklist.md](references/privacy-audit-checklist.md) | 隐私审计检查清单 | 推送前自查 |
| [references/pitfalls.md](references/pitfalls.md) | 32 条常见陷阱（致命/严重/注意/脚本纪律） | 执行下载/删种前回顾 |
| [references/env-reference.md](references/env-reference.md) | 完整环境变量清单 + 配置模板 | 配置或排查环境问题 |

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
| PTSkit (拾刻) | Cookie | `/special.php` 成人区 | ✅ `needs_proxy` | NexusPHP，短剧+成人 |
| PTHome (铂金家) | Cookie | 无 | ✅ `needs_proxy` | NexusPHP |
| HDSky (天雪) | Cookie | 无 | ✅ `needs_proxy` | NexusPHP |
| HDHome (家园) | Cookie | 无 | ✅ `needs_proxy` | NexusPHP |
| Audiences (观众) | Cookie | 无 | ✅ `needs_proxy` | NexusPHP |
| KeepFriends (朋友) | Cookie | 无 | ✅ `needs_proxy` | NexusPHP，Category 419 可能含成人内容 |
| ToTheGlory (TTG) | Cookie | 无 | ✅ `needs_proxy` | TBSource 自定义解析器，`/browse.php` 搜索，分类嵌入搜索字符串 |

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
| 电影/剧集名 | 影视 | → 全 15 站常规搜索 |
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
| PTSkit | `ptskit` | PTHome | `pthome` |
| HDSky | `hdsky` | HDHome | `hdhome` |
| Audiences | `audiences` | KeepFriends | `keepfrds` |
| ToTheGlory | `ttg` | Sukebei | `sukebei` |

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

## Jellyfin 集成（可选）

详见 [references/jf-integration.md](references/jf-integration.md)：连接配置、片库去重、关注列表（`pt_wishlist.json`）、每日追剧 cron。

## 成人内容（可选）

详见 [references/adult-content.md](references/adult-content.md)：javbus-api 部署与磁链获取、PTTime/M-Team/PTSkit 成人区搜索、公开磁链源与筛选、Cron 成人追剧链路。

## 新增 PT 站

详见 [references/new-site-adaptation.md](references/new-site-adaptation.md)：5 步适配流程（信息收集→平台识别→解析器→验证→文档更新）+ 适配检查清单。

**参考项目优先**：适配新站点时，必须先查阅以下两个开源项目的对应站点实现，作为标准参考：
- **PT-depiler**（`/tmp/opencode/research/PT-depiler/`）：PT 站点解析器、辅种逻辑、促销标签映射、Cookie 认证流程
- **MoviePilot**（`/tmp/opencode/research/MoviePilot/`）：站点适配、用户信息采集、促销类型识别、站点配置 schema

遇到不确定的解析逻辑、认证方式或字段映射时，优先对照这两个项目的实现，保持一致。

**手写解析器必须委托编程 agent**：NexusPHP 系站点只需注册 SITES 字典（零代码），Agent 可直接完成。但遇到非标框架需要手写解析器时（Case 3），Agent **禁止自己写代码**——先完成 Step A/B 的信息收集和 HTML 分析，然后将完整的解析规格（DOM 结构、字段映射、示例 HTML 片段）委托给 Claude Code / OpenCode 等专业编程 agent 实现和调试。

## Common Pitfalls

致命级 6 条（代理/公开种/去重/静默/确认闸门/M-Team禁Cookie）+ 严重级 7 条 + 注意级 12 条 + 脚本纪律 7 条。详见 [references/pitfalls.md](references/pitfalls.md)。

Agent 每次执行下载/删种前必须回顾致命级 1-6 条。

## 环境变量

完整清单见 [references/env-reference.md](references/env-reference.md)。模板见 `templates/secrets.env.example`。

关键规则：
- **禁止设 `HTTP_PROXY`** — 用 `PT_PROXY`
- 脚本通过 `_load_env_file()` 安全读取，禁止 `source secrets.env`
- API Key 写 `secrets.env`，不依赖 memory
