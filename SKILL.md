---
name: pt-claw.skill
description: "PT种子搜索下载与qBittorrent管理技能。搜索/下载/辅种/刷流/站点管理时触发——包括搜片、下片、详情页直推、qb管理、查做种、删种、辅种、查站内信息、刷流保号、Cookie同步、追剧等场景。115站支持(15核心+100扩展)，纯脚本无外部依赖。 Also use this skill when users ask about PT sites, torrent search, qBittorrent management, cross-seeding, ratio boosting, Jellyfin media integration, or any private tracker automation task."
version: 3.5.0
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
用户说"搜XXX" → 识别内容类型 → 路由到对应搜索 → ⚠️JF去重(权威!) → 下载历史去重 → 展示结果+元数据 → 排序 → 🛑用户确认 → 推送 qBittorrent → ① 验证种子已到达(URL可能已过期!) → ② 打站点标签+验证 → ③ 记录下载历史(pt_downloaded.json) → 下载完成 → 通知
```

**⚠️ JF 是权威来源**：`pt_downloaded.json` 不完整（可能漏记手动下载或旧渠道入库的影片）。搜索后、展示前，**必须先查 JF 去重**，再查下载历史。展示给用户的结果中必须标注「已在 JF」的条目（标 ✅ 而非 🆕），禁止把已有影片当新资源展示。详见 Agent 行为规则 #7。

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
- **M-Team 成人区**：通过 API 的 `mode: "adult"` 参数，分类 410-440。注意部分国产创作者在馒头用的是英文名（如「饼干姐姐」→「FortuneCutie」），中文关键词搜不到时尝试英文名。**日本女优同理**：M-Team 种子标题常使用罗马字英文名而非日文汉字（如「滝本雫葉」→「Takimoto Shizuha」），日文搜不到立即换英文名重搜
- **PTTime 成人区**：通过 `/adults.php` 路径，搜索参数 `search_area=1`
- **Sukebei（公开源）**：`sukebei_search.py` 是公开 tracker，无需 cookie，PT 站搜不到时作为回退
| Jellyfin | jf、JF、jellyfin、片库、去重、已存在 |

### 场景速查

| 用户说 | 路由 |
|--------|------|
| 「搜流浪地球2」「找个4K沙丘」 | → Step 1 识别类型 → Step 2 搜已配置站点（`--all` 搜全站） |
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
| `verify_javbus_proxy.py` | 本地服务代理门回归探针：javbus_star/javbus_magnet 对 localhost 不带代理、对远程带 PT_PROXY（改 `_http.py` 或代理逻辑后必跑，exit 0=全过） |
| `jf_query.py` | Jellyfin 查询 |
| `jf_batch_check.py` | 批量 JF 逐码拥有检查（从 secrets.env 读 JF1/JF2 凭据，JF1 优先 JF2 兜底；追剧 cron 批量去重用，123 码 ~2s） |
| `chase_crosscheck.py` | PT actor 搜索 vs javbus 片单交叉核对（找 M-Team 预发布/新上架；追剧 cron 流水线第 ⑥ 步） |
| `chase_extract.py` | javbus 片单候选提取 + 过滤（追剧 cron 流水线第 ② 步；编码 NONSTD/锚定前缀/OAE/排除厂牌/exclude_multi 规则，勿在 /tmp 手写临时脚本） |
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
| [references/jf-integration.md](references/jf-integration.md) | Jellyfin 连接配置 + 去重 + 追剧 + 关注列表 + 下载完成自动刷新 | 涉及 JF/追剧/去重/自动刷新 |
| [references/cron-progress-check.md](references/cron-progress-check.md) | Cron 进度检查 + 公开种清理 + 死种告警 | cron 进度监控配置或调试 |
| [references/adult-content.md](references/adult-content.md) | javbus-api + 成人区搜索 + 公开磁链 + 成人追剧链路 | 成人内容搜索/追剧/磁链 |
| [references/pt-boost.md](references/pt-boost.md) | PT 刷流配置 + 执行逻辑 | 刷流保号 |
| [references/new-site-adaptation.md](references/new-site-adaptation.md) | 新增 PT 站适配 5 步流程 | 用户要添加新站 |
| [references/mteam-api.md](references/mteam-api.md) | 馒头 API 端点 + 认证 + genDlToken | 涉及 M-Team |
| [references/diagnostic-network.md](references/diagnostic-network.md) | Cookie/代理/IP绑定诊断 + 代理变更检查清单 | 连接 403 或代理迁移时 |
| [references/media-maintenance.md](references/media-maintenance.md) | 媒体库重复检测 + 磁盘孤儿扫描 | 清理重复下载或手动恢复 |
| [references/privacy-audit-checklist.md](references/privacy-audit-checklist.md) | 隐私审计检查清单 | 推送前自查 |
| [references/cron-batch-patterns.md](references/cron-batch-patterns.md) | Cron 环境批量查询安全模式（JF/下载历史/PT搜索） + javbus_star 语法 | cron 追剧批量查询时 |
| [references/cron-chase-output-template.md](references/cron-chase-output-template.md) | Cron 追剧报告输出格式模板 | 编写 cron 追剧输出时 |
| [references/magnet-inspection.md](references/magnet-inspection.md) | 磁力链接 info hash 反查：不下载识别内容 | 用户提供 magnet link 想知道里面是什么 |
| [references/qb-session-auth.md](references/qb-session-auth.md) | qB Web API v5+ CSRF 认证（禁止 Basic Auth） | 手动 curl 调 qB API 或 403 时 |
| [references/site-tags.md](references/site-tags.md) | 115 站完整标签映射 | 推送下载时查找标签 |
| [references/extended-sites.md](references/extended-sites.md) | 扩展 100 站完整列表（URL/代理/分类） | 查看扩展站详情或配置 Cookie |
| [references/env-reference.md](references/env-reference.md) | 完整环境变量清单 + 配置模板 | 配置或排查环境问题 |
| [references/cron-chase-lessons.md](references/cron-chase-lessons.md) | Cron 追剧经验教训（javbus-api 坑、canary 假阳性、PT/JF 前缀不匹配、非标准内容过滤、M-Team 预发布、cron 批量查询安全模式） | 追剧 cron 出问题时 |
| [references/cron-pipe-patterns.md](references/cron-pipe-patterns.md) | Cron 管道安全模式（管道被拦截时的 stdin 重定向 + 批量脚本替代方案） | cron 遇到 pipe-to-interpreter 拦截时 |
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

**⚠️ 中文片名验证原则**：搜索中文/港产片名时，PT 站模糊匹配可能返回完全无关的英文片（如「火遮眼」→ "A Man Apart"；同一片名也可能正确命中 "The Furious"——**每次都必须验证**）。若结果标题/年份不匹配预期，用豆瓣 subject_suggest API（`curl "https://movie.douban.com/j/subject_suggest?q=<urlencoded 片名>"`，直连即可，返回 JSON 含 title/year/id）查准确英文名和别名，详情页元数据用 TMDB（走代理）兜底，再用英文名重新搜 PT。⚠️ 豆瓣 `subject_search` 页面 JS 渲染不出结果、详情页被 sec.douban.com 拦截，别用。未上映/刚上映的片 PT 零结果是常态，告知用户等资源即可，不要反复换关键词搜索。详见 pitfalls.md #62。

**番号判断正则**：`^[A-Z]{2,6}[-_ ]?\d{2,5}$`（不区分大小写）

| 国籍 | 搜索用名 |
|------|---------|
| 日本 | 日文原名（七緒，不是七绪） |
| 欧美 | 英文原名（Christopher Nolan，不是诺兰） |
| 韩国 | 韩文原名（박찬욱，不是朴赞郁） |
| 中国 | 中文原名 |

### Step 2：执行搜索

```bash
# 默认只搜已配置站点（有 Cookie 或 API Key 的站）
cd /home/alex/.hermes/skills/media/pt-claw && python3 scripts/pt_search.py "关键词" --limit 10

# 明确搜全部 115 站（含未配置的，会跳过无 Cookie 的站）
cd /home/alex/.hermes/skills/media/pt-claw && python3 scripts/pt_search.py "关键词" --all --limit 10

# 成人区搜索（仅 PTTime 和 M-Team）
cd /home/alex/.hermes/skills/media/pt-claw && python3 scripts/pt_search.py "SONE-833" --site pttime --adult --limit 10
```

**. 对策**：cron 追剧不要并行调 javbus_star.py。改用**顺序直连 curl**（不设代理，localhost 直连，必须用 `-G` + `--data-urlencode` 否则中文/日文 400）：`curl -sG -m 15 "http://localhost:8922/api/movies/search" --data-urlencode "keyword=演员名" --data-urlencode "type=normal" -o /tmp/jb_actorN.json`，然后统一用脚本批量处理 JF 去重。非 cron 环境可用 `sudo docker restart javbus-api && sleep 4` 恢复，但 cron 模式下审批拦截 → 直接跳过 javbus-api 走 PT 直搜。详见 [references/cron-chase-lessons.md](references/cron-chase-lessons.md)。

**⚠️ javbus-api 全量零返回（致命）**：Cron 追剧批量查询前先做金丝雀测试（query 一个已知演员验证 API 可用性）。所有演员都返回 0 → 容器级故障，立即跳过 javbus-api 全走 PT 直搜。详见 pitfalls.md #52a。

**⚠️ javbus-api canary 假阳性**：金丝雀测试通过（热门演员正常返回）不等于后续查询都能成功——已验证金丝雀用「三上悠亜」返回 30 条但紧随其后 4 个演员全部 502。金丝雀只是粗略存活信号，金丝雀通过 + 后续全 502 应当立刻回退 PT 直搜，不要逐个重试。详见 [references/cron-chase-lessons.md](references/cron-chase-lessons.md)。

**⚠️ PT actor search 不完整**：`pt_search.py "演员名"` 依赖种子标题含演员名，但 M-Team 英文标题和 PTTime 简略标题可能漏掉个别番号（已验证：楓ふうあ actor search 漏掉了 M-Team 有 5 个版本的 SONE-706）。PT actor search 后，对 javbus 片单中未出现在结果里的番号，挑最近 6 个月的逐码补搜 PT。详见 [references/cron-chase-lessons.md](references/cron-chase-lessons.md)。

**⚠️ PTTime adult --actor 限制**：`--actor` 参数不能搭配空 search query，会报 "No search query provided"。改用具体番号搜索。详见 pitfalls.md #54。

### Step 3：JF 去重 + 展示结果 & 排序

**⚠️ JF 先去重，再展示（必须！）**：PT 搜索结果拿到后，**禁止直接展示**。JF 去重必须分**两阶段**执行：

**阶段 1：演员名搜索（快速初筛）**
```bash
cd /home/alex/.hermes/skills/media/pt-claw
python3 scripts/jf_query.py --search "瀧本雫葉"   # 演员名（用日文原名）
```

**阶段 2：逐码验证（必须！消除假阴性）**
演员名搜索**不可信为完备**——JF 元数据中演员名标签常有变体（如"东云美怜"/"東雲みれい"/"Shinonome Mirei"混用），名字搜索会漏掉部分作品。阶段 1 过后，**必须对 PT 搜到的每个番号单独验证**：
```bash
# PT 搜到的每个番号逐个查 JF（cron 模式下禁止管道，逐条保存）
python3 scripts/jf_query.py --search "SSIS-491" > /tmp/jf_SSIS-491.json 2>&1
python3 scripts/jf_query.py --search "SSIS-522" > /tmp/jf_SSIS-522.json 2>&1
# ...
```

只有两阶段都通过后，才结合 `download_history.py filter` 做第三层过滤。JF + 下载历史都过一遍后，剩余的才是真正的新资源。

**⚠️ PT/JF 番号前缀不匹配（先验证再判定，别想当然）**：PT 站搜索结果中的番号前缀可能与 JF 中的实际编号不同（S1 rebrand 常见：SSIS↔SONE、SSNI↔SSIS）。JF 逐码返回 0 时，先交叉检查该演员的 JF 名单（`jf_query.py --search "演员名"`），确认是否已在 JF 但用了不同前缀。**但前缀不同 ≠ 一定是同一部作品**——必须先对比 javbus 的 title+date 确认两码是同一部片，才能标「已拥有」。已验证反例（2026-08-11）：PTTime 的 **SSIS-785**（逆おねだりビッチ，2023-07-21）与 JF 中的 **SONE-785**（新人スポーツキャスター，2025-07-18）是**两部不同作品**——08-09 报告按「前缀混标」误判 SSIS-785 已拥有而漏报，次日才纠正。判定步骤：① javbus 分别查两个码 → ② title+date 一致才合并视为同片 → ③ 不一致则 PT 码是独立新资源。详见 [references/cron-chase-lessons.md](references/cron-chase-lessons.md)。

展示结果时，JF 已有的条目必须显式标注 `✅ 已拥有`，不能混在「可下载」列表中让用户误以为没下过。

从 `user-preferences.md` 读取偏好（清晰度、编码），按以下优先级排序：

1. **匹配用户偏好**（清晰度 + 编码）— 不符合的排后面
2. **做种人数最多** — 下载更快
3. **体积较小** — 省空间

**📋 多作品逐个介绍**：搜到同一演员/导演的多部不同作品，必须逐一介绍（番号/年份/简介/大小/做种数）。让用户自己选。

**🎬 同名多版本歧义**：中文标题常同时存在电影/动画/剧集多个版本，必须分组展示并询问用户要哪个。

**做种不足时的处理**：PT 做种低于阈值 → 自动回退公开源（JavBus → Sukebei），不需要问用户。列出所有可行选项让用户选。

### Step 4：🛑 用户确认闸门（必须！禁止跳过！）

**搜到资源后绝不能直接下载。** 必须将结果汇总展示给用户，等待确认。

**⚠️ JF 交叉验证（展示前必做！）**：`download_history.py filter` 只能排除 `pt_downloaded.json` 中的条目，但该文件不完整（手动下载、旧渠道入库的种子不会记录）。展示结果前**必须用 `jf_query.py --search <番号>` 逐部查 Jellyfin**，JF 已有的标注「✅ 已有」而非「未下载」。`pt_downloaded.json` 是辅助手段，**JF 才是拥有状态的权威来源**。

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
# ⚠️ Cron 环境禁止管道：用 write_file 创建输入文件 + stdin 重定向
python3 scripts/download_history.py filter < /tmp/dl_check.txt   # 批量
```

**推送下载** — **必须使用两步法（本地下载 .torrent → `qb_add.py --file` 上传）**，详见 [references/qb-operations.md](references/qb-operations.md)。

**⚠️ 致命陷阱（已验证 BTSchool 中招）**：`python3 scripts/qb_add.py "https://pt.xxx.com/download.php?id=N"` 直接传 URL 会**静默失败**——API 返回 `success:true` 但种子永不出现。qB 自己去拉 URL 时没有 PT Cookie，被 PT 站拒绝。不只是 M-Team，**所有 PT 站（BTSchool/PTTime/CarPT 等）的 download.php 均受此影响**。

**唯一可靠方式**：
```bash
# Step 1: 用 PT Cookie 下载 .torrent 到本地
curl -s -o /tmp/xxx.torrent -H "Cookie: <从 secrets.env 取>" "https://pt.xxx.com/download.php?id=N"
# Step 2: 本地文件上传到 qB
python3 scripts/qb_add.py --file /tmp/xxx.torrent --tags <site> --category <分类>
# Step 3: 验证种子已到达（必须！）
python3 scripts/qb_monitor.py --full 2>&1 | grep -i "<片名>"
```
只有公开磁链（magnet:）和公开源 URL（Sukebei/JavBus）可用 URL 直推模式。禁止对 PT 站用 URL 推送（会静默失败）。

**⚠️ M-Team URL 时效性**：搜索返回的 M-Team 下载 URL 含 `t=<timestamp>` 签名参数，**时效极短（可能几分钟内过期）**。搜索与推送之间如有任何延迟（用户确认、大量结果逐个介绍、先推其他种子等），URL 会静默失效——`qb_add.py` 返回 `{"success": true}` 但种子永不到达 qB。对策：
- 批量推送时，M-Team URL 优先于其他站点推送（趁 URL 还新鲜）
- 推送 M-Team 种子后立即用 `qb_monitor.py --full` 验证种子已出现在列表中
- URL 过期时重新搜索（`pt_search.py`）获取新鲜 URL 再推
- dlv2 返回 302→Google 时：**先按 pitfalls.md #42b 精确头组合重试**（完整浏览器 UA + `Referer: https://www.m-team.cc/`，Referer host 写错 kp 子域会失效）→ 仍 302 才判服务器降级 → 回退公开源（javbus_magnet + sukebei_search）重新展示等用户确认，禁止凭一次换头失败就宣布「端点挂了」（详见 #42c）
- 详见 pitfalls.md #42 / #42b / #42c

**🏷️ 站点标签（必须！）**：

核心站标签速查：`mteam` / `pttime` / `btschool` / `carpt` / `hdfans` / `1ptba` / `soulvoice` / `zmpt` / `ptskit` / `pthome` / `hdsky` / `hdhome` / `audiences` / `keepfrds` / `ttg` / `sukebei` / `javbus`

完整 115 站标签映射见 [references/site-tags.md](references/site-tags.md)。标签 = 站点 ID（小写）。

推送成功后必须**先验证种子到达、再验证标签、最后记录历史**（严格顺序！严禁并行！）：

**① 验证种子已到达 qB（必须第一步！M-Team URL 静默过期陷阱）**：
M-Team 下载 URL 含签名时间戳，`qb_add.py` 返回 `{"success": true}` **不等于种子已在 qB**——URL 过期时推送静默失败，种子永不到达。**推送后立即**用 `qb_monitor.py --full` 确认种子已出现在列表中（按名称搜索）。若未找到 → 立即 `pt_search.py --site mteam --adult "<番号>"` 重新搜索获取新鲜 URL → 重新推送 → 再次验证。**验证通过前禁止进入下一步。**

**② 验证标签（必须在确认种子到达后）**：
确认种子在 qB 后，用 `qb_monitor.py --full` 回查标签。若缺失，用 `qb_add.py --retag <hash> --tags <tag>` 补打：
```bash
python3 scripts/qb_add.py --retag 2dc99206569795ac3cc6e009c9ff2b8c0fa18b72 --tags mteam
```
⚠️ **获取 hash 是必要例外**：`qb_monitor.py --full` 的 downloading 段不含 hash（见 pitfalls.md #43），而 `qb_add.py --retag` 需要 hash。唯一获取途径是查 qB API `/api/v2/torrents/info`（完整两行 curl 命令见 pitfalls.md #43a）。这是 `--retag` 获取 hash 的唯一可用路径，不算违规。其他操作仍禁止手写 curl/urllib。

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

详见 [references/jf-integration.md](references/jf-integration.md)：连接配置、片库去重、关注列表（`pt_wishlist.json`）、每日追剧 cron、下载完成自动刷新媒体库（`_cron_check.py` 内置，双实例 + 30 分钟限频 + 刷流目录跳过）。

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

致命级 10 条 + 严重级 8 条 + 注意级 26 条（含子条目）+ 脚本纪律 17 条，共 62 条。详见 [references/pitfalls.md](references/pitfalls.md)。

> **Cron job 禁止附加 pt-claw.skill**：不要用 `skills=["pt-claw.skill"]` 创建 cron 任务——整份 ~20KB SKILL.md 会被内联到每次运行的上下文，叠加通知输出后超出 `max_tokens` 上限导致截断。用自包含 prompt + `skills=[]` 替代（详见 #39 Cron prompt 设计铁律）。同时执行 `hermes config set model.max_tokens 32768` 拉满输出上限。完整排查步骤见 [references/cron-progress-check.md](references/cron-progress-check.md) "Cron 输出截断预防" 章节。

Agent 每次执行下载/删种前必须回顾致命级 1-7 条。

### ⚡ Agent 行为规则（非脚本，Agent 自身遵循）

**0. Cron 模式工具约束（致命级）。** Cron 环境下 `execute_code` 被阻止、`sudo docker restart` 需要审批、`| python3` 管道被安全扫描器拦截。必须使用以下安全模式：
- **所有输出保存到临时文件** → `python3 script.py > /tmp/result.json 2>&1`，然后用 `read_file` 读取
- **所有 stdin 输入通过临时文件** → `write_file` 创建输入文件 → `script.py < /tmp/input.txt`
- **javbus-api 不可用时**（502/404/"Not Found"/空返回）：先区分原因：`javbus_star.py` 通过代理访问 localhost 易 502 → 改用**顺序直连 curl**（`curl -s localhost:8922/api/movies/search?keyword=...`，不设代理，localhost 直连不经过 PT_PROXY）。直连也失败 → 容器异常，跳过 javbus-api 片单查询，直接 PT 成人区搜索 + JF 去重。HTTP 404 "Not Found" 与 502 同属容器异常，回退策略一致。`sudo docker restart javbus-api` 在 cron 模式可能被审批拦截
- **javbus-api 502 定因诊断（确定性故障，非并发瓶颈）**：`javbus_star.py` 报 `HTTP 502 fetching http://localhost:8922/...` 时，用 `curl -x <PT_PROXY> "http://localhost:8922/..."` 对比直连——走代理 502 / 直连 200 = **本地服务被误套 PT_PROXY**（代理把 localhost 解析成代理机自身，必然 502）。代码根因：`javbus_get()` 第 24 行 `proxy = _env("PT_PROXY") or None`。**✅ 已修复（2026-08-26）**：`javbus_star.py javbus_get()` 与 `javbus_magnet.py _get_json()` 均已改为 host-gated proxy（仅非 localhost 才带 PT_PROXY），修脚本时全局搜一下同类模式。Jellyfin（jf_query.py）未踩此坑。排查全流程见 [references/cron-chase-lessons.md](references/cron-chase-lessons.md)「追剧 cron 静默排查」节
- **禁止任何管道接解释器**（`curl | python3`、`python3 | python3`、`for ... | python3 -c` 全部拦截）：用 `curl -o /tmp/x.json` / `python3 script.py > /tmp/x.json 2>&1` + `read_file` 替代
- **禁止 `for ... | python3 -c` 循环管道**：批量 JF 查询时逐条 `python3 jf_query.py --search "CODE" > /tmp/jf_CODE.json 2>&1` 保存，最后用 shell `for f in /tmp/jf_*.json; do python3 -c "import json;..." $f; done` 读取本地文件（此模式不触发管道拦截）
- **javbus-api `type=star` 无效**：搜索演员必须用 `type=normal`。`type=star` 返回 `"query is invalid"` 错误。正确用法：`curl -sG "http://localhost:8922/api/movies/search" --data-urlencode "keyword=演员名" --data-urlencode "type=normal"`。详见 [references/cron-chase-lessons.md](references/cron-chase-lessons.md)
- **非标准内容过滤**：`REBD-`（写真DVD）、`SIVR-`（VR/8K）、`MBDD-`（写真集）、`OFJE-`（精选合集）、`PFES-`（多人共演/写真）、`FWAY-`（写真DVD/FAIR＆WAY）、`OAE-`（混合：标题含 ALL NUDE 为写真，OAE-287 等为正常剧情片，按标题判断）、`SS-`（写真/ETERNAL）为非标准 AV 内容；BEAUTY VENUS 系列（IPZZ-623/586）为 IP 社多人共演标志，exclude_multi 演员自动排除。VR 内容 PT 站有做种但 JF 通常不收录，追剧报告标注即可，不作为重点推荐。详见 [references/cron-chase-lessons.md](references/cron-chase-lessons.md)

**1. 优先用现成脚本，禁止手写 Python 查 qB。** `qb_monitor.py --full` 一行就能拿到全部信息。`--states`、`--stalled`、`--codes` 覆盖所有查询场景。禁止自己写 `urllib` 登录 qB API。

**2. 用户问"下载好什么"→ 先查 cron 最新输出。** 种子完成→清理后 qB 里就没了。`~/.hermes/cron/output/<job_id>/` 最新文件才是权威来源。qB → 下载历史 → JF → cron 输出，按这个顺序查。

**3. 删种文件保留规则：**
- 下载完成(100%) → 保留文件（用户可能要看）
- 未完成/死种/metaDL → 连带删文件（废片占空间）
- `qb_monitor.py --delete` 默认保留文件，未完成需追加 qB API `deleteFiles=true`

**4. 禁止管道接 `python3 -c` 过滤 JSON。** 脚本输出是结构化的，LLM 直接读就行。过滤用脚本自带的 `--codes`/`--tags`/`--states` 参数，不要 `| python3 -c "import sys,json; ..."`。这是手写 Python，违反规则 1。读取脚本完整输出让 LLM 自己解析 JSON 是零成本的，管道过滤反而多此一举。

**5. 推送后必须验证标签。** `qb_add.py` 推送后用 `qb_monitor.py --full` 查回确认标签打上了。没打上用脚本补打（禁止手写 curl/urllib 调 qB API）。

**6. 脚本功能有缺口 → 直接汇报用户，不自己写代码绕过。** 某个操作现有脚本都做不到时（如「补标签」），直接告诉用户：「缺 XXX 功能，现有脚本覆盖不了」。等用户明确允许后再动手（委托 OpenCode 加功能，或手动 curl 一次）。禁止自己写 Python/curl/管道 JSON 绕过——这是「脚本缺口汇报」规则，与规则 1「优先用现成脚本」和规则 4「禁止管道接 python3 -c」是三位一体的纪律。

**7. JF 才是拥有状态的权威来源，pt_downloaded.json 不可信。** 搜索展示前必须先查 JF。`pt_downloaded.json` 可能漏记手动下载、旧渠道入库或从其他机器同步的影片。流程必须是 JF → download_history → 展示。禁止只查 download_history 就告诉用户「都没下过」——这是虚假信息。用户纠正过：「我下载过 你jellyfin是不是搜错了？」——这句话就是规则 #7。

**⚠️ 规则 #7 补遗：JF 演员名搜索不完备。** `jf_query.py --search <演员名>` 依赖 JF 元数据中的演员标签，而标签常有变体混用（如"东云美怜"/"東雲みれい"/"Shinonome Mirei"三种写法共存）。演员名搜索后会漏掉部分作品（已验证案例：東雲みれい名搜返回 11 部，实际 JF 中有 14 部）。因此追剧 dedup 必须两阶段：① 演员名初筛 → ② PT 搜到的每个番号逐码验证 `--search <CODE>`。只有逐码查 JF 返回 `total > 0` 才算「已拥有」。

**8. 委托编程 agent 的三重验证门（缺一不可）。** omp/OpenCode 落地后只跑 `git diff + py_compile` 不够——已实战踩坑（2026-09-02）：omp 实现了 JF 刷新功能且代码全对，但它同时写的文档引用了两个**代码里根本不存在的环境变量**（`JF_REFRESH_MIN_INTERVAL_MINUTES`/`JF_REFRESH_SKIP_PATHS`，实际是硬编码）。委托方擅长把文档写得比代码更美好。第三道门：对它写/改的每一份文档，grep 核实其中提到的环境变量名、CLI 参数、state 键名、配置键**是否真的在代码里存在**。文档吹代码没有的功能 = 未来排障时按文档操作必然失败。

**9. 文档分层：skill 机制与用户配置分开放（用户明确要求）。** 更新 skill 文档时：**通用机制**（脚本行为、API 用法、限频/排除逻辑等对任何人生效的内容）→ 写进 `references/*.md` + `SKILL.md`；**用户个性化配置**（实例地址分工、目录含义如「/downloads 是纯刷流」、阈值、开关）→ 写进 `user-preferences.md`（不入 Git）。两边互相用一句话指路（references 里注明「实例分工等用户配置见 user-preferences.md」，反之亦然），禁止把用户的具体配置硬编码进 skill 通用文档。

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

