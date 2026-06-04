# Common Pitfalls — 常见陷阱与纪律

## 致命级

**1. bash `source secrets.env` 会因 cookie 特殊字符报错**：Cookie 值含 `==`、`;`、`=` 等字符时，`source` 会触发 bash 解析错误（如 `sl-session=xxx==: 未找到命令`）。**永远用 Python `_load_env_file()` 读取环境变量**，不要 source。手动调试时用 Python 单行脚本。

**2. PTTime 成人区搜索必须走 `adults.php`**：`pt_search.py --adult` 对 PTTime 走 `/adults.php?search=...&search_area=1&incldead=1`（注意参数是 `search=`，不是旧版 `searchstr=`）。`--adult --actor` 同理走 `/adults.php?search=...`。早期 `searchstr=` 参数曾失效，但 `search=` 参数正常工作。

**3. 公开磁链只看标签不看 tracker**：唯一可靠判断是 qB 标签（sukebei/javbus）。`qb_public_cleanup.py` 有四道防线：占比>20%中止、单次≤50、`--check` 先查后删、删除前自动备份。

**4. 下载历史防重复**：推送成功立即写 `pt_downloaded.json`。去重第一优先——历史中有 = 无条件跳过。

**5. `[SILENT]` 不能和内容混用**：含 `[SILENT]` 整条静默。有事件发摘要，互斥。

**6. 确认闸门——下载和删种都经用户确认**：搜到资源禁止直接推送；三个删种脚本必须 `--check` 先查后删；cron 只搜索不下载。

**7. M-Team 禁止 Cookie 登录**：馒头严禁 Cookie 方式访问，会封号。只能 `MTEAM_API_KEY` REST API。`cookie_sync.py` 不为 mteam 同步，`connectivity_check.py` 不测 mteam cookie。

## 严重级

**8. M-Team API**：①限速 403（1000次/24h）②下线 405 ③DNS 302 ④**国内 IP 直连 403，必须走 PT_PROXY**。`mteam_api.py` 和 `pt_search.py` 在 `PT_PROXY` 未设置时直接报错，不会静默直连。

**9. qB URL 推送静默失败**：PT 站 download.php 需 Cookie，qB 没有。两步法见 [qb-operations.md](qb-operations.md)。

**10. JF 已有 ≠ 重复**：比 `DateCreated` vs qB `added_on` 时间戳。JF 晚于 qB = 正常入库。

**11. API key 必须写 `secrets.env`**：不依赖 memory。用 `printf >>` 追加。

**12. PT 恢复种子结构不匹配**：本地 .torrent → snatchlist → 搜索下载。导入后验证命中已有文件。

**13. wishlist 厂牌排除同步**：用户说「XXX 厂牌不要」→ 立即更新 `exclude_prefixes`。

**14. 同名多版本分组展示**：电影/动画/剧集分别列出，让用户选。

## 注意级

**15. 成人搜索必须检查开关**：搜索前读 `user-preferences.md` 的 `## 成人内容 → 启用` 字段。`enabled: false` 或未配置 → 拒绝成人搜索请求，告知「成人内容未启用，如需开启请修改 user-preferences.md」。`enabled: true` → 正常走成人搜索链路：PTTime 用 `adults.php?search=...&search_area=1&incldead=1`、M-Team 成人区（`mode: "adult"`）、PTSkit `/special.php`、做种不足→javbus-api + Sukebei。

**16. 演员走元数据不搜 PT**：javbus-api `/api/movies/search?keyword=&page=N`。JF 逐条查。

**17. 日本演员用日文汉字**：「七緒」能搜，「七绪」0 结果。先用番号反查获取原名。

**18. JF/javbus-api 中文 URL 编码**：`--data-urlencode` 或 `urllib.parse.quote()`。

**19. 公开磁链**：JavBus > Sukebei（磁链多/去码/AI）、`--list-files`→用户确认→`--select-files`、`--max-video` 兜底、下完删种保文件、卡死换不同 hash。

**19b. JavBus 磁链获取需两步**：`javbus_magnet.py --api` 返回的是电影详情（封面/演员/gid/uc），不是磁链列表。获取磁链的正确流程：
1. `GET /api/movies/{code}` → 提取 `gid` 和 `uc`
2. `GET /api/magnets/{code}?gid=X&uc=Y` → 获取结构化磁链列表（含大小/HD/字幕标记）
一步到位命令：
```bash
gid=$(curl -s "http://localhost:8922/api/movies/$CODE" | python3 -c "import sys,json; print(json.load(sys.stdin)['gid'])")
uc=$(curl -s "http://localhost:8922/api/movies/$CODE" | python3 -c "import sys,json; print(json.load(sys.stdin)['uc'])")
curl -s "http://localhost:8922/api/magnets/$CODE?gid=$gid&uc=$uc"
```

**20. 三重去重**：下载历史 → JF 搜索 → JF `DateCreated` vs qB `added_on`。

**21. 搜老剧多关键词**：中文通用标题 + 季别名 + 英文名+季号。

**22. Cookie 403 ≠ 过期**：NexusPHP `c_secure_*` cookie 绑定登录 IP。直连 403 → 走代理重试（代理出口 IP 需和浏览器一致），代理也 403 → 才判过期。详见 [diagnostic-network.md](diagnostic-network.md)。

**23. PTTime Cloudflare 拦截**：browser_navigate 抓或等冷却。

**24. PT_PROXY 变更需同步 javbus-api**：修改 `secrets.env` 中 `PT_PROXY` 后，javbus-api 的 Docker 容器仍使用旧代理。需同步更新 `docker-compose.yml` 中 `HTTP_PROXY`/`HTTPS_PROXY` 并重建容器。路径：`~/javbus-api/docker-compose.yml`。完整步骤见 [diagnostic-network.md](diagnostic-network.md)。

**25. `connectivity_check.py` 消耗 M-Team 配额**：`test_mteam()` 每次调 `POST /torrent/search {"keyword":"test"}`，消耗 1000次/24h 配额。频繁调用（如 cron 每次跑）会导致 API 限速 403。诊断流程：先查是否频繁调了 `connectivity_check.py`，而非直接怀疑 API key。

**26. `pt_notify_state.json` 通知状态文件**：`_cron_check.py` 用此文件追踪死种通知频率（首次立即，之后每 6h 提醒，最多 20 次）。文件不存在时自动创建默认值，无需手动维护。不要删除此文件，否则会丢失通知计数导致重复提醒。

**26a. PTTime 成人搜索参数是 `search=` 不是 `searchstr=`**：早期 `adults.php?searchstr=` 曾失效返回全量，后改用 `adults.php?search=` 恢复正常。`pt_search.py --adult` 当前走 `/adults.php?search=...&search_area=1&incldead=1`，与 #2 一致。不要改回 `searchstr=` 参数。

**26b. Cookie 过期检测只看 `<title>` 标签**：之前检测 `'登录' in html[:2000]` 会把导航栏的「快捷登录」文字误判为过期。已改为提取 `<title>` 标签内容再检测（`_common._is_login_page()`）。涉及文件：`pt_search.py`、`site_profile.py`、`connectivity_check.py`。不要改回 `html[:N]` 方式。

**26c. TTG 列索引从表头动态解析**：TTG 页面列顺序可能变化，硬编码索引（6/7/8）不可靠。已改为解析 `<th>` 表头行建立 名称→索引 映射（匹配 大小/Size、完成/Completed、做种-下载/S-L），仅在表头未找到时回退到硬编码默认值。

**26d. JavBus 爬取健壮性**：`javbus_magnet.py` 的 `search_scrape` 已加固：① gid/uc 正则支持 `var/let/const` + 灵活空白 ② bigImage 匹配多值 class 属性 ③ 样例图匹配任意 CDN 域名（不限 pics.dmm.co.jp）④ 磁链支持 base32 hash ⑤ 爬取前检测 CAPTCHA/Cloudflare/重定向。遇到「Movie not found」时先检查是否被 CAPTCHA 拦截。

## 脚本纪律

**27. qb_add.py 磁链推送超时回退**：`qb_add.py --stdin` 的 `max_video` 模式会等待元数据取回，对慢磁链可能超时。超时时回退到直接 qB API 推送：`curl -b <cookie> -X POST '<qb_url>/api/v2/torrents/add' --data-urlencode 'urls=<magnet>'`，然后补 `setCategory` + `setLocation` + `addTags`。

**28. 禁止 `source secrets.env`**：Cookie 值含 `=`，bash source 会误解析。脚本内部 `_load_env_file()` 安全处理。

**29. 禁止手写内联 Python，包括 `| python3 -c` 管道过滤**：
- 禁止 `| python3 -c "import sys,json; ..."`——脚本输出本身就是结构化 JSON，LLM 直接读就行，不需要再过滤。
- 禁止手写 `urllib` 调 qB API——`qb_monitor.py --full` 一行搞定。`--states`/`--stalled`/`--codes`/`--tags` 覆盖所有过滤场景。
- 禁止 `python3 -c "from _qb_session import ..."`——这是绕开脚本自己写代码。
- **为什么这样写会被说**：用户一眼看出你在手写 Python 解析 JSON，而不是用脚本。点号 (`|`) 后面接 `python3 -c` 在对话里特别显眼，触发「你怎么又在写脚本」的反弹。
- **脚本做不到 → 直接汇报缺口，禁止自己补**：如果某个操作（如给已有种子补标签、查特定字段）现有脚本覆盖不了，直接告诉用户「缺 XXX 功能，现有脚本做不到」。等用户明确允许后再解决（委托 OpenCode 或手动 curl 一次）。禁止因为「脚本没有这个功能」就自己写 Python 绕过——这恰恰是用户最讨厌的模式。Skill 的 Agent 行为规则第 6 条（脚本缺口汇报）与本条是三位一体纪律。

**30. 内网用 Python 脚本不裸 curl**：tirith 拦截 curl→私有 IP。脚本内部 `urllib.request` 绕过。

**31. `write_file` 替换敏感值**：写 `secrets.env` 用 `printf >>`。

**32. 全量隐私审计（每次推送前自查）**：API Key、内网 IP、路径、用户 ID 绝不硬编码。见 [privacy-audit-checklist.md](privacy-audit-checklist.md)。

**33. 新增脚本的 Cookie 检测必须复用 `_is_login_page()`**：`_common.py` 提供了 `_is_login_page(html)` 公共函数，通过提取 `<title>` 标签内容检测登录页面。禁止在新脚本中使用 `'登录' in html[:N]` 之类的粗暴匹配——会把导航栏「快捷登录」等文字误判为 Cookie 过期。所有 Cookie 有效性检测统一走这个函数。

**34. 查下载进度时别忘了 cron 输出**：公开磁链完成后会被 `_cron_check.py` 自动删种（种子从 qB 消失，文件保留）。此时 qB API / `pt_downloaded.json` / `pt_deleted_backup.json` 都看不到有效完成记录。正确的查询链路：**最近一次 cron 报告 → qB 当前种子 → 下载历史 → deleted_backup**。Cron 输出在 `~/.hermes/cron/output/<job_id>/`。用户问「今天下载好的」优先查 cron 报告，不要在 qB 里找不到就回答「没有」。

**35. qBittorrent Web API v5+ 必须 session 认证**：直接 `curl -u user:pass` 或 Python `urllib` Basic Auth 返回 403 Forbidden。正确流程：① `POST /api/v2/auth/login`（body: `username=xxx&password=xxx`）获取 `Set-Cookie: SID=...` → ② 后续请求带 `Cookie: SID=xxx`。`_qb_session.py` 已内置此逻辑，`qb_monitor.py` 和 `qb_add.py` 已适配。手动 curl 调 qB API 时必须遵守两步法，见 [qb-session-auth.md](qb-session-auth.md)。

**36. Agent 排查时只给结论，不要主动问「要不要修」**：用户说「检查下脚本是否通？说结论别去改」「别修复」——排查类任务用户要的是状态报告和根因分析，不是修复建议。发现 bug 后只报告，不主动提议修复，除非用户明确要求。这与脚本修复类任务不同（后者当然要修）。

**37. `_env()` 优先读 `secrets.env` 再回退 `os.environ`（已修复）**：`_common._env()` 当前正确实现：先用 `secrets.env`（通过 `_env_cache`），文件未命中才回退到 `os.environ`。早期曾存在 bug 导致 `os.environ` 优先，已于 v3.0.x 修复。如遇旧配置残留：`unset PT_PROXY` 后重跑脚本验证，或重启 Hermes。

**38. `qb_add.py --tag` 不保证生效，推送后必须验证标签**：`qb_add.py` 的 `--tag` 参数依赖 qB API `addTags` 调用时机，可能在种子元数据未就绪时静默失败。推送后必须用 `qb_monitor.py --full` 回查验证标签字段非空。若缺失，可用 `qb_add.py --retag` 重打标签（截至 v3.1.0 已支持）。验证步骤作为 Step 5 的强制收尾，不可跳过。

**39. Cron agent 禁止全盘搜索文件**：cron 任务已设 `workdir` 指向 skill 目录，脚本和配置都在当前目录下。Agent 必须直接用相对路径执行（如 `python3 scripts/cookie_sync.py`），禁止跑到 `/home/alex` 全盘搜索。搜不到就报「未安装/未配置」→ 纯粹是 agent 无视 prompt 自己发挥。

**Cron prompt 设计铁律**（实战验证——只说「做什么」不够，必须说「不许做什么」）：
- 开头必须声明：`工作目录已设为 skill 目录，scripts/ 和 secrets.env 都在当前目录下，禁止全盘搜索文件，直接用相对路径执行`
- **文件存在性幻觉防御**：即使 prompt 明确写了「skill 目录下已有 X、Y、Z 文件」，cron agent 仍可能间歇性输出「X 不存在，请初始化」。必须在 prompt 尾部显式禁止：`禁止检查文件是否存在——文件必定存在，直接执行流程` + `禁止输出"尚未初始化""文件不存在"等初始化检查信息`。典型反例：PT 追剧 cron 在 6/3 明明工作正常（前两日均正常执行），却突然报告 `pt_wishlist.json、secrets.env、user-preferences.md 均不存在` 并拒绝执行——纯模型幻觉，文件完好无损。
- 成功路径必须显式收窄：`同步成功（exit 0）→ [SILENT]`、`连接检查全通 → [SILENT]`
- 失败路径必须限制篇幅：`用一句话报告哪个环节挂了`、`用一句话报哪个站挂了`
- 尾部必须加禁止清单：`禁止生成诊断报告、文件列表、初始化建议等废话`
- 模糊指令（如「全部正常则 [SILENT]」）不够——agent 会在「不正常」时自由发挥整页报告。每条分支都要写死输出格式。
- 所有 cron job prompt 遵循此规则。典型反例：CookieCloud 同步 prompt 没有显式禁止全盘搜索，agent 无视 workdir + skill 脚本，直接 `/home/alex` 全局搜然后报「未安装」。

**41. 演员名歧义——同姓不同人**：Sukebei/JavBus 等公开源对演员名做子串匹配，搜「東雲」会同时返回 東雲みれい 和 東雲つばき 的作品。VEC-771 是東雲つばき的，不是東雲みれい的。输出结果时必须核实：①用番号反查 `/api/movies/{CODE}` 确认演员列表 ②看完整标题是否含全名而非仅姓氏 ③不同演员的作品分组标注「注意：XXX 是另一位演员」。不要看到同姓就归给一个演员。

**42. JavBus 全线 521 时的回退链**：JavBus 返回 521（Cloudflare origin down）时，javbus-api 完全不可用。此时演员信息获取的回退顺序：① Sukebei 搜演员名 → 提取番号列表 ② Sukebei 搜番号 → 读标题获取演员+剧情 ③ JF 实例搜索。注意 Sukebei 的上传日期 ≠ 发行日期，排序仅作参考。javbus-api 恢复后优先用 API 核实。

**43. M-Team 签名下载 URL 时效短 + curl 代理返回 HTML**：`/api/rss/dlv2?sign=...&t=<timestamp>` 的 `t` 参数是时间戳，过期极快（可能几分钟内）。搜索返回的下载 URL 不可久存，推送前必须重新调用 `python3 scripts/mteam_api.py download <torrent_id>` 获取新鲜 URL。更隐蔽的是：`curl -x <proxy> <download_url>` 有时返回 Google HTML 而非 .torrent 文件（代理层面的问题），但 Python `urllib.request` + ProxyHandler 走同一代理则正常下载。下载 .torrent 时优先用 Python urllib 而非 curl。

**44. `qb_monitor.py --full` 下载中种子无 hash 字段**：`--full` 输出的 `downloading` 列表中每个条目只有 `name/progress/size/dlspeed/tags/state`，**不包含 `hash` 字段**。这意味着种子正在下载时无法通过 hash 精确匹配来验证标签。补标签时只能用 `name` 子串匹配定位，或用 `qb_add.py` 推送时返回的 `info_hash`。一旦种子完成（移入 `completed_recent`），hash 字段恢复。

**45. `qb_add.py --file` 静默假成功（v3.3.0 已修复）**：`qb_add.py` 现已支持 `--file` 模式，通过 multipart form upload 正确上传本地 .torrent 文件。旧版 `--file` 被静默吞掉导致假成功的问题已修复。用法：`python3 qb_add.py --file /tmp/xxx.torrent --category 9kg --tags mteam`。上传前会验证文件存在且以 `d`（bencode dict 标记）开头。

**46. `qb_add.py --retag` 补标签功能（v3.1.0+）**：`python3 qb_add.py --retag <hash> --tags mteam` 给已有种子打标签。此功能不在 `--help` 输出中但已实现。注意 hash 参数格式：`--retag abc123` 或 `--hash=abc123`。与 pitfall #38（`--tag` 不保证生效）配合使用——推送后标签缺失时用此补打。

**47. 愿望单管理（v3.3.0+ 支持脚本命令）**：`wishlist_manager.py` 提供 `add-actor`/`remove-actor`/`add-movie`/`remove-movie`/`add-fanhao`/`remove-fanhao`/`list`/`json` 命令，支持 `exclude_multi`、`exclude_prefixes` 字段。cron 追剧搜到演员作品列表后，agent 应过滤掉标题含「共演」「×」「&」「ハーレム」等多演员标记的作品（当该演员设了 `exclude_multi: true`）。

**48. `qb_add.py --recat` 补分类功能（v3.3.0+）**：`python3 qb_add.py --recat <hash> --category "电影"` 给已有种子设置分类。与 `--retag`（补标签）对称使用。hash 参数格式：`--recat abc123` 或 `--hash=abc123`。

**40. 番号忽略名单（v3.3.0+ 支持脚本命令）**：`download_history.py ignore --code FWAY-071 --reason "不喜欢"` 将番号标记为 ignored，`check`/`filter` 自动跳过。取消忽略用 `unignore --code FWAY-071`。也可手动写入 `pt_downloaded.json`（status 设 `"ignored"`，source 设 `"manual"`）。

**49. `site_profile.py` 无 `--site` 时自动过滤已配置站点（v3.3.0 已修复）**：默认只查询有 Cookie 或 MTEAM_API_KEY 的站点，不再遍历全部 115 站。`--all` 恢复原行为。`--debug` 输出 HTML 片段辅助 NexusPHP 解析诊断。

**51. qB API `torrents/info` 批量列表不返回完整 hash，禁止截取使用**：`/api/v2/torrents/info?sort=added_on&reverse=true&limit=N` 返回的条目中 `hash` 字段是完整的 40 字符 SHA1。但 **Agent 用 `terminal()` 执行 Python 脚本列出时，输出可能被截断**（如只显示前 12 字符 `ddee9cb7a9e4`）。如果拿截断的 hash 去调 `--retag`、`setCategory`、`setLocation` 等 API，会静默失败（hash 不匹配，qB 返回空响应不报错）。**正确做法**：推送新种子后，用 `qb_monitor.py --full` 查看完整状态（含完整 hash），或用 `torrents/info?hashes=<full_hash>` 精确查询。必须验证 hash 长度 = 40 字符再用于任何 API 调用。从批量列表获取 hash 时，用 `len(hash)` 验证 40 字符，不满足就重新精确查询。

**50. NexusPHP 站用户信息解析不完整（v3.3.0+ 支持 `--debug` 诊断）**：`site_profile.py` 用正则从 HTML 提取字段，不同站 HTML 结构差异大导致解析不全。`--debug` 模式输出原始 HTML 片段（`info_html_excerpt`、`matched_labels`、`page_title`）辅助逐站适配。已知影响：1PTBar / CarPT / 织梦 / BTSchool / HDFans / PTTime / SoulVoice 共 7 站。仅 M-Team（走 API）数据完整。
