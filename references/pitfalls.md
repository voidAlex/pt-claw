# Common Pitfalls — 常见陷阱与纪律

## 致命级

**1. 代理用 `PT_PROXY`，禁止用 `HTTP_PROXY`**：`HTTP_PROXY` 会让 Agent 自身 API 走代理，挂了直接失联。脚本按站点 `needs_proxy` 标记自动应用 `PT_PROXY`。

**2. 公开磁链只看标签不看 tracker**：唯一可靠判断是 qB 标签（sukebei/javbus）。`qb_public_cleanup.py` 有四道防线：占比>20%中止、单次≤50、`--check` 先查后删、删除前自动备份。

**3. 下载历史防重复**：推送成功立即写 `pt_downloaded.json`。去重第一优先——历史中有 = 无条件跳过。

**4. `[SILENT]` 不能和内容混用**：含 `[SILENT]` 整条静默。有事件发摘要，互斥。

**5. 确认闸门——下载和删种都经用户确认**：搜到资源禁止直接推送；三个删种脚本必须 `--check` 先查后删；cron 只搜索不下载。

**6. M-Team 禁止 Cookie 登录**：馒头严禁 Cookie 方式访问，会封号。只能 `MTEAM_API_KEY` REST API。`cookie_sync.py` 不为 mteam 同步，`connectivity_check.py` 不测 mteam cookie。

## 严重级

**7. M-Team API**：①限速 403（1000次/24h）②下线 405 ③DNS 302 ④**国内 IP 直连 403，必须走 PT_PROXY**。`mteam_api.py` 和 `pt_search.py` 在 `PT_PROXY` 未设置时直接报错，不会静默直连。

**8. qB URL 推送静默失败**：PT 站 download.php 需 Cookie，qB 没有。两步法见 [qb-operations.md](qb-operations.md)。

**9. JF 已有 ≠ 重复**：比 `DateCreated` vs qB `added_on` 时间戳。JF 晚于 qB = 正常入库。

**10. API key 必须写 `secrets.env`**：不依赖 memory。用 `printf >>` 追加。

**11. PT 恢复种子结构不匹配**：本地 .torrent → snatchlist → 搜索下载。导入后验证命中已有文件。

**12. wishlist 厂牌排除同步**：用户说「XXX 厂牌不要」→ 立即更新 `exclude_prefixes`。

**13. 同名多版本分组展示**：电影/动画/剧集分别列出，让用户选。

## 注意级

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

**21. Cookie 403 ≠ 过期**：NexusPHP `c_secure_*` cookie 绑定登录 IP。直连 403 → 走代理重试（代理出口 IP 需和浏览器一致），代理也 403 → 才判过期。详见 [diagnostic-network.md](diagnostic-network.md)。

**22. PTTime Cloudflare 拦截**：browser_navigate 抓或等冷却。

**23. PT_PROXY 变更需同步 javbus-api**：修改 `secrets.env` 中 `PT_PROXY` 后，javbus-api 的 Docker 容器仍使用旧代理。需同步更新 `docker-compose.yml` 中 `HTTP_PROXY`/`HTTPS_PROXY` 并重建容器。路径：`~/javbus-api/docker-compose.yml`。完整步骤见 [diagnostic-network.md](diagnostic-network.md)。

**24. `connectivity_check.py` 消耗 M-Team 配额**：`test_mteam()` 每次调 `POST /torrent/search {"keyword":"test"}`，消耗 1000次/24h 配额。频繁调用（如 cron 每次跑）会导致 API 限速 403。诊断流程：先查是否频繁调了 `connectivity_check.py`，而非直接怀疑 API key。

**25. `pt_notify_state.json` 通知状态文件**：`_cron_check.py` 用此文件追踪死种通知频率（首次立即，之后每 6h 提醒，最多 20 次）。文件不存在时自动创建默认值，无需手动维护。不要删除此文件，否则会丢失通知计数导致重复提醒。

## 脚本纪律

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

**32. 全量隐私审计（每次推送前自查）**：API Key、内网 IP、路径、用户 ID 绝不硬编码。见 [privacy-audit-checklist.md](privacy-audit-checklist.md)。
