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

**39. Cron agent 禁止全盘搜索文件**：cron 任务已设 `workdir` 指向 skill 目录，脚本和配置都在当前目录下。Agent 必须直接用相对路径执行（如 `python3 scripts/cookie_sync.py`），禁止跑到 `/home/alex` 全盘搜索。搜不到就报「未安装/未配置」→ 纯粹是 agent 无视 prompt 自己发挥。Cron prompt 应显式禁止全盘搜索、禁止生成诊断报告、禁止建议初始化流程。所有 cron job prompt 遵循此规则。

**40. 番号忽略名单用 `pt_downloaded.json`**：没有独立的 ignore 文件。要忽略某个番号（不再出现于搜索/追剧结果），直接写入 `pt_downloaded.json`，status 设为 `"ignored"`，source 设为 `"manual"`。`download_history.py check/filter` 只判断番号存在性，不区分 status，所以 ignored 条目自动被跳过。写入时注意加 `reason` 字段记录原因。
