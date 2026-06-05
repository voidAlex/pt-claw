---
name: pt-claw.skill
description: "PT种子搜索下载与qBittorrent管理技能。搜索/下载/辅种/刷流/站点管理时触发——包括搜片、下片、详情页直推、qb管理、查做种、删种、辅种、查站内信息、刷流保号、Cookie同步、追剧等场景。115站支持(15核心+100扩展)，纯脚本无外部依赖。 Also use this skill when users ask about PT sites, torrent search, qBittorrent management, cross-seeding, ratio boosting, Jellyfin media integration, or any private tracker automation task."
version: 3.3.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [pt, torrent, qbittorrent, download, media, nas, mteam, adult, jav, 辅种, 刷流]
    related_skills: []
---

# pt-claw.skill — PT 多站搜索下载与 qBittorrent 管理

## Overview

通过对话搜索 115 个 PT 站资源、推送到 qBittorrent 下载、完成后通知。纯脚本实现，无 Prowlarr/Jackett 依赖。

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

**115 站支持（15 核心 + 100 扩展）**：核心站 → PTTime · M-Team(馒头) · BTSchool · CarPT · HDFans · 1PTBar · SoulVoice · 织梦 · PTSkit · PTHome · HDSky · HDHome · Audiences(观众) · KeepFriends(朋友) · ToTheGlory(TTG)；扩展站 → PTer(猫站) · HDArea · CHDBits · OurBits · HDDolby · HDKylin · HDTime · HDU · HhanClub(憨憨) · 海胆 · 天使 · 春天(CMCT) · TCCF(ET8) · TLF(吐鲁番) · JoyHD · 北洋 · 葡萄(SJTU) · 北邮人(BYRBT) · 蝴蝶(HUDBT) · 南洋PT · 龟站(KamePT) 等 100 站

## When to Use

以下任意关键词或场景触发本技能加载：

### 触发词

| 分类 | 关键词 |
|------|--------|
| 搜索/下载 | 搜、搜索、下载、下、找个资源、有没有、求片 |
| 详情页直推 | 详情页、链接下载、这个种子、直推、直接下 |
| qBittorrent | qb、qB、qbit、下载进度、下载状态、做种、种子、删种、暂停、恢复、死种 |
| 辅种 | 辅种、cross seed、检查辅种、哪些站能辅、批量辅种、全站辅种 |
| PT 站点 | pt、PT、PT站、馒头、mteam、pttime、btschool、carpt、hdfans、1ptba、1PTBar、一PT吧、soulvoice、zmpt、织梦、ptskit、拾刻、pthome、铂金家、hdsky、天雪、hdhome、家园、audiences、观众、keepfrds、朋友、ttg、套套哥、听听歌、totheglory、pter、猫站、hdarea、chdbits、彩虹岛、ourbits、我堡、hddolby、高清杜比、hdkylin、麒麟、hdtime、hdupt、好多油、hhanclub、憨憨、海胆、hdcity、天使、springsunday、春天、cmct、tccf、et8、tlfbits、吐鲁番、joyhd、tjupt、北洋、sjtu、葡萄、byrbt、北邮人、hudbt、蝴蝶、nanyangpt、南洋、kamept、龟站、rousi、肉丝、opencd、皇后、烧包、唐门 |
| 番号/成人 | 番号、车牌、jav、JAV、成人、sukebei、javbus、nyaa |
| 定时任务 | 定时任务、cron、追剧、刷流、下载通知 |
| 关注/收藏 | 关注、取消关注、关注列表、wishlist |
| 用户信息 | 分享率、用户信息、上传量、下载量、做种积分、站点数据 |
| 刷流保号 | 刷流、保号、freeleech、促销种、ratio boost |
| Cookie 同步 | cookie同步、CookieCloud、同步cookie、更新cookie |
| 下载历史 | 下载历史、下过什么、历史记录、忽略名单 |
| 连接测试 | 连接测试、通不通、站点可达、环境检查 |
| Jellyfin | jf、JF、jellyfin、片库、去重、已存在 |

### ⚠️ 成人区搜索 — 必须加 `--adult` 标志

`pt_search.py` 默认搜索**普通区**，不包含成人/9kg 区。搜索成人内容（番号、国产创作者如饼干姐姐、JAV）时**必须**加 `--adult`：

```bash
python3 pt_search.py "饼干姐姐" --adult                          # 全站成人区搜索
python3 pt_search.py "饼干姐姐" --site mteam --adult              # 单站成人区
python3 pt_search.py "饼干姐姐" --site pttime --adult             # PTTime 成人区走 /adults.php
```

不加 `--adult` 时，M-Team 走普通搜索（不含 adult mode），PTTime 走普通种子列表，结果大概率是 0 条。

**站点差异**：
- **M-Team 成人区**：通过 API 的 `mode: "adult"` 参数，分类 410-440。注意部分国产创作者在馒头用的是英文名（如「饼干姐姐」→「FortuneCutie」），中文关键词搜不到时尝试英文名
- **PTTime 成人区**：通过 `/adults.php` 路径，搜索参数 `search_area=1`
- **Sukebei（公开源）**：`sukebei_search.py` 是公开 tracker，无需 cookie，PT 站搜不到时作为回退
| Jellyfin | jf、JF、jellyfin、片库、去重、已存在 |

### 场景速查

| 用户说 | 路由 |
|--------|------|
| 「搜流浪地球2」「找个4K沙丘」 | → Step 1 识别类型 → Step 2 全站搜索 |
| 「下SSIS-448」「搜SONE-833」 | → 番号 → 成人区搜索 + 公开源回退 |
| 「查下载进度」「qb怎么样了」 | → 先查最新 cron 报告（种子可能已被自动清理，qB 里没了但 cron 输出有记录），然后 `qb_monitor.py` |
| 「删掉那个死种」「暂停xxx」 | → qB API 操作 |
| 「关注诺兰」「收藏SSIS-xxx」 | → `wishlist_manager.py add` → `pt_wishlist.json` |
| 「恢复」「qb种子丢了」 | → [references/qb-operations.md](references/qb-operations.md) |
| 「首次配置」「初始化」 | → [references/first-time-setup.md](references/first-time-setup.md) |
| 「新增一个PT站」 | → [references/new-site-adaptation.md](references/new-site-adaptation.md) |
| 「辅种」「哪些站能辅」「cross seed」 | → `cross_seed.py` — 多站辅种验证与推送 |
|| 「这个链接下载」「详情页推送」 | → `pt_download.py` — 详情页 URL 直接下载推送 qB |
|| 「这是什么种子」「magnet链接识别」 | → [references/magnet-identify.md](references/magnet-identify.md) — 通过 info hash 识别种子内容 |
| 「查各站用户信息」「我的分享率」 | → `site_profile.py` — 多站用户信息查询（默认只查已配置站） |
| 「刷流保号」「freeleech 辅种」 | → `pt_ratio_boost.py` — Freeleech 自动辅种刷流保号 |
| 「同步 Cookie」「CookieCloud」 | → `cookie_sync.py` — CookieCloud Cookie 同步 |
| 「环境检查」「配置对不对」 | → `env_check.sh` — 环境变量完整性检查 |
| 「下载历史」「下过什么」 | → `download_history.py` — 下载历史追踪（check/list/filter） |
| 「连接测试」「各站通不通」 | → `connectivity_check.py` — 全服务连接测试 |
| 「这个磁力是什么」「仅检查不下载」 | → [references/magnet-inspection.md](references/magnet-inspection.md) — 磁力链接 info hash 反查内容 |

## 脚本清单

所有脚本用法、参数说明和命令示例见 [references/scripts-guide.md](references/scripts-guide.md)。

| 脚本 | 用途 |
|------|------|
| `pt_search.py` | 多站搜索（115 站 NexusPHP + M-Team API） |
| `pt_download.py` | 详情页 URL 或 `--site/--torrent-id` 直接下载推送 qB（通用所有站） |
| `qb_add.py` | 添加种子到 qBittorrent（含文件选择 + `--file` 本地上传 + `--recat` 补分类） |
| `qb_monitor.py` | qB 状态/过滤/删除/死种诊断 |
| `cross_seed.py` | 多站辅种验证与推送 |
| `site_profile.py` | 多站用户信息查询（v3.3.0+ 默认只查已配置站，`--debug` 诊断模式） |
| `pt_ratio_boost.py` | Freeleech 刷流保号 |
| `qb_snapshot.py` | 删种备份与恢复 |
| `qb_public_cleanup.py` | 公开磁链清理 |
| `_cron_check.py` | Cron 综合检查（完成/死种/清理） |
| `connectivity_check.py` | 全服务连接测试 |
| `cookie_sync.py` | CookieCloud 同步 |
| `download_history.py` | 下载历史防重复（含 ignore/unignore 忽略名单） |
| `wishlist_manager.py` | 愿望单管理（add/remove/list 演员/影片/番号，支持 exclude_multi、exclude_prefixes） |
| `mteam_api.py` | M-Team API 客户端 |
| `sukebei_search.py` | Sukebei RSS 搜索 |
| `javbus_magnet.py` | JavBus 磁链爬取 |
| `javbus_star.py` | 演员片单交叉对比 |
| `jf_query.py` | Jellyfin 查询 |
| `env_check.sh` | 环境变量检查 |

> **内部模块**（`_` 前缀脚本）：`_common.py`（公共工具）、`_http.py`（HTTP 客户端）、`_logger.py`（日志系统）、`_qb_session.py`（qB 会话）、`_search_cache.py`（搜索缓存）— 不直接调用，被其他脚本引用。

所有脚本通过 `_logger.py` 统一写入 `logs/pt-claw.log`（RotatingFileHandler，10MB × 6 份 = 最大 60MB）。每次调用自动分配 8 字符 `call_id`，贯穿整个调用链。排障时查看日志：
```bash
grep "call_id" logs/pt-claw.log | tail -50    # 最近调用
grep "ERROR" logs/pt-claw.log | tail -20       # 最近错误
```

## 数据文件

| 文件 | 用途 | Schema 文档 |
|------|------|------------|
| `pt_boost.json` | 免费种自动下载配置 | `references/pt-boost.md` |
| `pt_downloaded.json` | 下载历史记录 | `templates/pt_downloaded.example.json` |
| `pt_wishlist.json` | 想看清单（演员支持 `exclude_prefixes` 排除厂牌、`exclude_multi` 排除多人共演） | `references/jf-integration.md` |
| `pt_notify_state.json` | 通知状态 | `references/cron-progress-check.md` |
| `pt_deleted_backup.json` | 删种备份记录 | `templates/pt_deleted_backup.example.json` |
| `pt_completed_last.txt` | 已完成种子hash | `references/cron-progress-check.md` |
| `pt_search_cache.json` | 搜索缓存 | 内部使用，自动管理 |
| `cross_seed_tasks.json` | 跨站辅种任务 | 内部使用，自动管理 |

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
| [references/pitfalls.md](references/pitfalls.md) | 常见陷阱（致命/严重/注意/脚本纪律） | 执行下载/删种前回顾 |
| [references/magnet-inspection.md](references/magnet-inspection.md) | 磁力链接 info hash 反查：不下载识别内容 | 用户提供 magnet link 想知道里面是什么 |
| [references/qb-session-auth.md](references/qb-session-auth.md) | qB Web API v5+ CSRF 认证（禁止 Basic Auth） | 手动 curl 调 qB API 或 403 时 |
| [references/site-tags.md](references/site-tags.md) | 115 站完整标签映射 | 推送下载时查找标签 |
| [references/extended-sites.md](references/extended-sites.md) | 扩展 100 站完整列表（URL/代理/分类） | 查看扩展站详情或配置 Cookie |
| [references/env-reference.md](references/env-reference.md) | 完整环境变量清单 + 配置模板 | 配置或排查环境问题 |
| `user-preferences.md` | 用户偏好配置（分类映射、保存路径、选项开关）|

日志路径：`logs/pt-claw.log`（自动轮换，最多 60MB）。

## Supported PT Sites

### Core 15 Sites

| 站点 | 接入 | 成人区 | 代理 | 备注 |
|------|------|--------|------|------|
| M-Team (馒头) | REST API | ✅ API `mode: "adult"` 已验证（分类 410-440） | ✅ **必须** | POST，`x-api-key` header，**禁 Cookie**，**国内 IP 直连 403，必须走 PT_PROXY** |
| PTTime | Cookie | `adults.php` 成人区（`/adults.php?search=...&search_area=1&incldead=1`） | ❌ | `data=` attribute 变体 |
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

### Extended 100 Sites (NexusPHP)

所有扩展站均为 Cookie + NexusPHP 模式，只需配置 `PT_COOKIE_<SITEID>` 即可使用。完整列表见 [references/extended-sites.md](references/extended-sites.md)。

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
| 电影/剧集名 | 影视 | → 全 115 站常规搜索 |
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

核心站标签速查：`mteam` / `pttime` / `btschool` / `carpt` / `hdfans` / `1ptba` / `soulvoice` / `zmpt` / `ptskit` / `pthome` / `hdsky` / `hdhome` / `audiences` / `keepfrds` / `ttg` / `sukebei` / `javbus`

完整 115 站标签映射见 [references/site-tags.md](references/site-tags.md)。标签 = 站点 ID（小写）。

推送成功后必须验证和记录：

**验证标签**：`qb_add.py` 的 `--tag` 参数不一定生效，推送后必须用 `qb_monitor.py --full` 回查确认标签。若缺失，用 `qb_add.py --retag <hash> --tags <tag>` 补打：
```bash
python3 scripts/qb_add.py --retag 2dc99206569795ac3cc6e009c9ff2b8c0fa18b72 --tags mteam
```
⚠️ 此步骤禁止手写 curl/urllib 调 qB API——只允许用现有脚本。

**记录下载历史**：
```bash
python3 scripts/download_history.py add --code <番号> --title "<标题>" --source <站点标签>
```

**分类映射**：首次初始化时从 qBittorrent API 读取分类列表，自动写入 `user-preferences.md`。后续直接从 `user-preferences.md` 读取。不硬编码分类名。

⚠️ **成人内容路径歧义**：qB 可能有多个人相关分类（如"9kg"→JAV、"其他"→国产/creative）。推送前用 `python3 scripts/qb_monitor.py --list categories` 列出全部分类，让用户选择路径。禁止自作主张全推到一个路径。详见 pitfalls.md #52。

### Step 6：后台定时任务

> 定时任务在 [references/first-time-setup.md](references/first-time-setup.md) 的初始化流程中自动创建。

| 任务 | 频率 | 通知条件 |
|------|------|---------|
| PT下载进度检查 | 每 15 分钟 | 完成/死种（首次立即，之后每 6h 提醒，最多 20 次）/公开种自动清理 |
| PT自动追剧 | 每天 10:00 | 有新资源（只展示不下载） |
| CookieCloud定时同步 **或** PT站点Cookie保活 | 每4h/每天06:00 | 同步成功/连接全通→[SILENT]；失败/异常→一句话报障 |

管理：「暂停XX任务」「恢复XX任务」「列出定时任务」

### 愿望单管理

```bash
python3 scripts/wishlist_manager.py add-actor --name "三上悠亜" --type adult_actress --exclude-multi --exclude-prefixes "VR,3D"
python3 scripts/wishlist_manager.py add-movie --title "流浪地球2"
python3 scripts/wishlist_manager.py add-fanhao --code SSIS-448
python3 scripts/wishlist_manager.py remove-actor --name "三上悠亜"
python3 scripts/wishlist_manager.py list
```

- `--exclude-multi`：排除多人共演作品
- `--exclude-prefixes "VR,3D"`：排除指定厂牌/标签前缀
- 追剧 cron 每日自动遍历 wishlist 搜索新资源

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

致命级 8 条 + 严重级 7 条 + 注意级 19 条（含子条目）+ 脚本纪律 17 条，共 51 条。详见 [references/pitfalls.md](references/pitfalls.md)。

> **Cron job 禁止附加 pt-claw.skill**：不要用 `skills=["pt-claw.skill"]` 创建 cron 任务——整份 ~20KB SKILL.md 会被内联到每次运行的上下文，叠加通知输出后超出 `max_tokens` 上限导致截断。用自包含 prompt + `skills=[]` 替代（详见 #39 Cron prompt 设计铁律）。同时执行 `hermes config set model.max_tokens 32768` 拉满输出上限。完整排查步骤见 [references/cron-progress-check.md](references/cron-progress-check.md) "Cron 输出截断预防" 章节。

Agent 每次执行下载/删种前必须回顾致命级 1-7 条。

### ⚡ Agent 行为规则（非脚本，Agent 自身遵循）

**1. 优先用现成脚本，禁止手写 Python 查 qB。** `qb_monitor.py --full` 一行就能拿到全部信息。`--states`、`--stalled`、`--codes` 覆盖所有查询场景。禁止自己写 `urllib` 登录 qB API。

**2. 用户问"下载好什么"→ 先查 cron 最新输出。** 种子完成→清理后 qB 里就没了。`~/.hermes/cron/output/<job_id>/` 最新文件才是权威来源。qB → 下载历史 → JF → cron 输出，按这个顺序查。

**3. 删种文件保留规则：**
- 下载完成(100%) → 保留文件（用户可能要看）
- 未完成/死种/metaDL → 连带删文件（废片占空间）
- `qb_monitor.py --delete` 默认保留文件，未完成需追加 qB API `deleteFiles=true`

**4. 禁止管道接 `python3 -c` 过滤 JSON。** 脚本输出是结构化的，LLM 直接读就行。过滤用脚本自带的 `--codes`/`--tags`/`--states` 参数，不要 `| python3 -c "import sys,json; ..."`。这是手写 Python，违反规则 1。读取脚本完整输出让 LLM 自己解析 JSON 是零成本的，管道过滤反而多此一举。

**5. 推送后必须验证标签。** `qb_add.py` 推送后用 `qb_monitor.py --full` 查回确认标签打上了。没打上用脚本补打（禁止手写 curl/urllib 调 qB API）。

**6. 脚本功能有缺口 → 直接汇报用户，不自己写代码绕过。** 某个操作现有脚本都做不到时（如「补标签」），直接告诉用户：「缺 XXX 功能，现有脚本覆盖不了」。等用户明确允许后再动手（委托 OpenCode 加功能，或手动 curl 一次）。禁止自己写 Python/curl/管道 JSON 绕过——这是「脚本缺口汇报」规则，与规则 1「优先用现成脚本」和规则 4「禁止管道接 python3 -c」是三位一体的纪律。

## 环境要求

**推荐模型**: DeepSeek V4 Pro（或其他支持长上下文、多工具调用的模型）

- Python 3.10+
- `python3-cryptography` (CookieCloud 同步需要)
- qBittorrent Web UI 已开启
- PT 站 Cookie（存于 `secrets.env`）
- M-Team API Key（可选，API 搜索需要）

## 环境变量

完整清单见 [references/env-reference.md](references/env-reference.md)。模板见 `templates/secrets.example.env`。

关键规则：
- 禁止在**系统环境**设 `HTTP_PROXY`（会影响所有脚本的正常网络请求）— 需要代理时用 `PT_PROXY`。Docker 容器（如 javbus-api）内部可单独设置 `HTTP_PROXY`。
- 脚本通过 `_load_env_file()` 安全读取，禁止 `source secrets.env`
- API Key 写 `secrets.env`，不依赖 memory

## 致谢

本技能在 PT 站适配过程中参考了以下优秀项目：
- [PT-depiler](https://github.com/tongl123/PT-depiler) - NexusPHP 站点解析参考
- [MoviePilot](https://github.com/jxxghp/MoviePilot) - 部分功能设计灵感

