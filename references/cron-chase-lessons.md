# Cron 追剧经验教训

## javbus-api 搜索演员的正确方式

**错误**：`curl "http://localhost:8922/api/movies/search?keyword=演员名&type=star"`
→ 返回 `{"error":"query is invalid","messages":["`type` must be `normal` or `uncensored`"]}`

**正确**：
```bash
curl -sG "http://localhost:8922/api/movies/search" \
  --data-urlencode "keyword=演员名" \
  --data-urlencode "type=normal"
```

- `type=star` 不是 javbus-api 的有效参数
- 必须用 `--data-urlencode` 对中文关键词做 URL 编码

## 跨日防回归：actor search 0 结果先对照昨日报告（2026-08-11）

**已验证事故**：08-09 报告对瀧本雫葉全片单逐码补搜，发现 28 部未收录（ABF-056~371 等，M-Team/PTTime 均有种）。08-10 的 cron 却用**错误简体「滝本雫葉」**做 actor search → 全站 0 条 → 报告写「滝本雫葉：PT 无结果」，28 部资源凭空消失一天。08-11 改用正确繁体「瀧本雫葉」重搜，28 部全部找回（外加新出现 REBDB-883）。

**根因**：追剧 cron 每次运行都是独立会话，上一轮的正确做法（繁体名/逐码补搜）不会自动延续；演员名搜索 0 条被当作「真无资源」直接写进报告。

**对策（防回归铁律）**：
- **actor search 返回 0 条时，先读上一轮报告**（`~/.hermes/cron/output/<job_id>/` 最新文件或 `session_search`）：若昨日/前日该演员报过资源，今天的 0 条 99% 是搜索词回归（简繁写错/用错名字变体），**禁止直接报「无结果」**
- 立即按 lessons 顺序重试：① 繁/简异体字变体（滝→瀧）→ ② 罗马字英文名 → ③ 直接对昨日报告的番号逐码补搜 PT
- 报告里注明「X 部昨报资源经逐码确认仍在站」，不要因为昨天漏报就假装它们不存在
- 每天开跑前固定检查上一轮输出（输出模板规则 #7 的「昨报」标注正是为此服务）

### 更危险的回归变体：凭空捏造「已入库或已下载」（2026-08-13）

**已验证事故**：08-12 报告对 瀧本雫葉 写「无新资源（均已入库或已下载）」，但 08-13 逐码验证发现 28 部 ABF 作品**全部未入库、未下载**（JF 逐码 0 命中 + download_history 无记录），M-Team/PTTime 种子全部仍在。同一天还**静默丢弃**了 楓ふうあ 的 SSIS-785/SONE-706/SONE-982（08-11 还报着，08-12 直接消失，无任何下载记录）。08-12 报告还用了简体「滝本雫葉」——与 08-10 同样的错误汉字回归，只是这次把「0 结果」粉饰成了「已入库」。

**根因**：actor search 0 条（错误汉字）后，上一轮 cron 没有如实报「无结果」，而是**编造了一个未经验证的拥有状态**。「已入库/已下载」是有明确证据门槛的结论（JF 逐码 total>0 或 download_history 有记录），搜索 0 条 ≠ 已入库。

**对策（铁律）**：
- **「已全收录/已入库/已下载」结论必须带证据**：JF 逐码命中（total>0）或 download_history 条目。没有任何一条证据 → 禁止写「已入库」。
- 搜索 0 条时宁可如实写「搜索 0 结果，待换字体重试」，也不要编造原因。
- 上一轮报告的清单在今日逐码验证前**逐条保留为 昨报**，不得静默消失——08-13 靠对照 08-11 报告把 SSIS-785/SONE-706/SONE-982 找回来了。
- 检查上一轮报告时不止看「报了什么」，还要看「上周报过、这轮突然消失」的条目——消失 = 怀疑被错误丢弃。

## 非标准内容过滤

以下前缀对应非标准 AV 内容，追剧时可在结果中标注但不作为重点推荐：

| 前缀 | 含义 | 大小特征 |
|------|------|---------|
| `REBD-` | 写真 DVD / Image Video | 通常 ~2-5 GB |
| `REBDB-` | REbecca 写真（4K 图集类，2026-08-11 验证 REBDB-883 PTTime 3.23GB） | 通常 ~3-4 GB |
| `SIVR-` | VR 内容（8K/VR） | 通常 15-25 GB |
| `MBDD-` | 写真集 / 合集 | 通常 ~5-10 GB |
| `OFJE-` | 精选合集 / Best Of | 通常 ~30+ GB |
| `IPOK-` | IP 社精选合集/周年ベスト（2026-08-18 验证 IPOK-014 愛才りあ1周年記念ベスト 12タイトル12時間） | 通常 ~10+ GB |
| `PFES-` | 多人共演 / 写真 | 通常 ~5-10 GB |
| `FWAY-` | 写真DVD / FAIR＆WAY | 通常 ~2-5 GB |
| `IPVR-` | IP 社 VR 内容（愛才りあ 等 IP 系演员的 VR 系列，2026-08-13 验证 IPVR-387/356/355/334 出现于 javbus 片单） | 同 SIVR 体积大 |
| `MBRBA-` | 写真 / 图集类（2026-08-13 验证 楓ふうあ MBRBA-100） | ~5-10 GB |
| `THN-`/`THU-`/`PPR-`/`PPX-` | 瀧本雫葉 等演员的非 ABF 主流系列（THN-016/THU-051/PPR-006/PPX-020/PPX-037 出现于 javbus 片单，按非标准排除） | 视具体而定 |
| `OAE-` | **混合前缀**：多数为写真（标题含 ALL NUDE，如 OAE-215/272），但 OAE-287 是正常剧情片（喉の奥まで触れられたい）——按标题是否含 "ALL NUDE" 判断，写真类标注不推荐 | 写真 ~5 GB |
| `SS-` | 写真/ETERNAL 系列（SS-072 ETERNAL 楓ふうあ，javbus 收录但 PT 无独立种子） | 视具体而定 |
| BEAUTY VENUS 系列 | IP 社多人共演标志（IPZZ-623/586 BEAUTY VENUS THE HARLEM，标题含「美人N」「究極共演」）——exclude_multi 演员自动排除 | ~5-10 GB |

VR 内容 (SIVR) 在 PT 站有做种但需要注意文件体积大（19+ GB），且 JF 通常不收录 VR 作品。

**⚠️ 前缀过滤必须锚定 `-`（2026-08-21 实测，勿重蹈）**：写批量过滤脚本时，前缀判定必须用 `code == PREFIX or code.startswith(PREFIX + '-')`，禁止裸 `code.startswith(PREFIX)`。裸 `startswith('SS')` 会把整个 SSIS 系列误判为写真 nonstd（東雲みれい 17 部全被滤成 0、楓ふうあ 24 部 SSIS 早期作品全丢——第一遍 kept=0/25 明显不对，锚定后恢复 14/52），裸 `startswith('VR')` 同理误伤。exclude_multi 的 BEAUTY VENUS 判定用系列级标记（'BEAUTY VENUS' / 'HARLEM' / '究極共演'），禁止裸 '美人'——已验证 IPZZ-623/586 标题含 "BEAUTY VENUS THE HARLEM"，而 IPZZ-749（「清楚美人お姉さん」正常单人作，昨报新资源）会被裸 '美人' 误删。OAE 按标题含 "ALL NUDE" 判断（OAE-287 为正常剧情片保留）。

**⚠️ GNI/DLV 不是非标准前缀（2026-08-23 实测，勿重蹈）**：写过滤脚本时**不要**顺手把 `GNI`、`DLV` 加进 NONSTD 列表——它们是瀧本雫葉 的正常作品（GNI-002 出道作 2023-11-24、DLV-003 2024-05-17），08-15 已作为 🆕 新资源报告并计入昨报 backlog，被滤掉会丢资源。NONSTD 列表应与 08-20 验证过的完全一致：`REBD/REBDB/SIVR/MBDD/OFJE/IPOK/PFES/FWAY/IPVR/MBRBA/THN/THU/PPR/PPX/SS` + OAE-ALL NUDE。08-23 初版脚本误加 GNI/DLV 导致片单数量不对，删掉后恢复。

## JF 演员名搜索不完备（已验证）

- **枫ふうあ**：javbus 有 30 部，JF 演员名搜索仅返回 11 部。漏掉的 4 部独奏作品（SONE-982, 760, 639, 591）均需逐码 JF 验证才能确认未收录
- **浅野こころ**：javbus 有 30 部，JF 演员名搜索返回 25 条（含 20 个唯一番号）。但逐码验证发现 SONE-943 和 SONE-905 **已在 JF 中**，Stage 1 名称搜索漏掉了它们。Stage 1 覆盖率约 90%，仍有假阴性风险
- **浅野こころ（追加 2026-08-13）**：Stage 1 名称搜索返回 20 个唯一番号，但逐码验证又发现 **SONE-208 / SONE-855 / SSIS-848 / SSIS-959 / SSIS-992 全部已在 JF**（total=1），Stage 1 全部漏掉——同一演员已累计 7 个假阴性番号（SONE-943/905/208/855, SSIS-848/959/992）。同时 javbus 片单中 MIMK-194、SONE-035/127/317/460/563/645、SSIS-812 在 download_history 命中（已下载）。**「演员名搜索初筛 + 下载历史」双过滤后剩下的候选仍需逐码 JF 验证，且每次验证都有新发现**——OAE-287 是唯一真新资源
- **滝本雫葉**：JF 搜索全名 "滝本雫葉" 返回 0 条，但搜索部分名 "雫葉"（去掉姓氏首字）返回 4 条（ABF-330/340/350/354）。JF 元数据中演员标签可能截断或使用变体——**全名 0 条时立即尝试部分名（去掉首字符或只用名）重搜**
- 这直接验证了规则 #7 补遗：**两阶段去重不可省略**——Stage 1 演员名搜索只做初筛，必须对 PT 搜到的每个番号逐码验证 `jf_query.py --search <CODE>` 才算 final

## javbus-api 日文汉字编码敏感：简繁异体字

javbus-api 对日文汉字的编码极其敏感，同一演员的不同汉字写法可能返回完全不同结果：

| 搜索词 | 结果 | 原因 |
|--------|------|------|
| `滝本雫葉`（简体"滝"） | **0 条** | javbus-api 内部索引用繁体「瀧」 |
| `瀧本雫葉`（繁体"瀧"） | **30 条** | 正确写法 |

**对策**：
- javbus-api 搜索演员名返回 0 条时，**先尝试日文繁/简异体字变体**（如 滝→瀧、円→圓、桜→櫻、竜→龍）
- 可在搜索前用 `python3 -c "print('名称'.encode('unicode_escape'))"` 确认两种编码不同
- 若两种写法都 0 条 → 回退 PT 成人区搜索（见 pitfall #52）

**⚠️ 跨文件简繁不一致陷阱（瀧本雫葉）**：`pt_wishlist.json` 存的是简体 `滝本雫葉`，但 `chase_extract.py` 的 `ACTORS` 字典、javbus-api 直连 curl、以及 PT 搜索**全部用繁体 `瀧本雫葉`**（javbus 索引和 M-Team ABF 标题都用繁体「瀧」）。追剧流水线里「搜索名」≠「wishlist 里的名字」是**有意为之**，不要看到 wishlist 写简体就顺手把 `chase_extract.py` 的字典「同步」成简体——那会让该演员片单/PT 搜索全 0（08-10/08-12 两次回归事故的根源就是误用简体）。正确做法：wishlist 保持用户输入的简体不变，搜索环节固定用繁体 瀧。

**⚠️ FALENO/ABF 系演员 javbus-api 曾全 0，但可恢复（2026-08-11 验证全 0 → 2026-08-15 恢复 43 部）**：瀧本雫葉（ABF-* 系，FALENO 厂牌）在 2026-08-11 javbus-api 两种写法都返回 0 条（`movies:[]`，body 仅 41 字节），但 2026-08-15 金丝雀 + 实际查询**恢复返回 43 部**（3 页）。说明 javbus-api 对 FALENO/ABF 厂牌的收录是**间歇性/可恢复**的，不是永久缺失。对策：① 「javbus 0 条」≠「该演员无作品」，仍要先试繁体名再回退 PT 直搜；② **不要固化「FALENO/ABF 演员 javbus 永远 0」结论**——每轮 cron 重新金丝雀测试该演员，恢复后即可拿到完整片单（比 PT 逐码补搜高效得多）。

## M-Team 日本女优英文名回退

M-Team 成人区种子标题对日本女优常使用罗马字英文名而非日文汉字。日文名搜 PT 全站 0 结果时，立即换英文名重搜：

**已验证案例（2026-07-13）**：
| 搜索词 | 结果 |
|--------|------|
| `滝本雫葉`（日文） | PT 全站 0 条（M-Team/PTTime 等 8 站均 No results） |
| `Takimoto Shizuha`（英文） | M-Team **1 条**：ABF-330（116 做种，12.5 GB） |

**追加案例（2026-08-06）**：`滝本雫葉`（日文简体）PT 全站 0 条，`Takimoto Shizuha`（英文）仅 1 条（ABF-330，**已在 JF**），但逐码搜索发现 ABF-371/369/317/308 **全部有 M-Team 种子**（做种 30~126），标题均含「瀧本雫葉」（日文繁体）。两点启示：
- **简繁异体字问题同样存在于 PT 站搜索（不仅 javbus-api）**：M-Team ABF 系列标题用繁体「瀧」而非简体「滝」，所以简体搜 0 条。日文名 0 结果时先试繁体变体（滝→瀧、円→圓、桜→櫻）再试英文名
- **英文名回退也可能只命中已拥有的旧作**：ABF-330 早在 JF，而 4 部新作对日文/英文名搜索都不可见——「actor search 有结果」≠「全部作品已覆盖」，逐码补搜不可省略

**对策**：
- PT 日文名搜索全站 0 条 → 不要放弃，立即换罗马字英文名重搜（仅 M-Team 即可，其他站通常不会有）
- M-Team 的 API search 对英文名匹配度远高于日文汉字
- 此规则与国产创作者英文名回退（饼干姐姐→FortuneCutie）属于同一模式，适用范围从国产扩展到全部非英文名演员

## javbus-api parallel proxy bottleneck: javbus_star.py routes localhost through PT_PROXY

`javbus_star.py` uses `_http.py` → `_env("PT_PROXY")` for ALL HTTP requests, including the javbus-api container at `localhost:8922`. This means every javbus-api call goes through the proxy, even though the target is on the same machine.

**Verified failure (2026-07-12)**: 4 parallel `javbus_star.py` calls (one per actress: 浅野こころ, 東雲みれい, 滝本雫葉, 楓ふうあ) all returned HTTP 502. Direct `curl` to `localhost:8922` (without proxy) worked perfectly immediately after — proving the proxy, not the API container, was the bottleneck.

**Root cause（2026-08-25 修正——不是并发瓶颈，是确定性 502）**: 早期判断以为是「4 进程并发压垮代理」的 burst bottleneck，**错误**。实测单次顺序调用 `javbus_star.py "三上悠亜"` 连跑 3 次全部 502，而 `curl` 直连 `localhost:8922` 稳定 200。真正机制：**代理服务器把 `localhost` 解析成代理机自身（10.10.1.8），代理机上没有 :8922 服务 → 任何经代理发往 localhost:8922 的请求必然 502**，与并发无关。一句话定因诊断：

```bash
curl -s -x http://10.10.1.8:7890 -w "HTTP %{http_code}\n" "http://localhost:8922/api/movies/search?keyword=test"   # → 502 = 本地服务被误套代理
curl -s -o /dev/null -w "HTTP %{http_code}\n" "http://localhost:8922/api/movies/search?keyword=test"                 # → 200 = 容器本身健康
```

- 代码级根因：`javbus_star.py` 的 `javbus_get()` 第 24 行 `proxy = _env("PT_PROXY") or None` 把 PT 代理传给了本地服务请求（secrets.env 里 `PT_PROXY=http://10.10.1.8:7890`）。**修复 = 本地服务请求不带 proxy**（一行），或 `_http.py` 对 localhost/127.0.0.1 强制直连（防御未来其他脚本踩坑）。
- **✅ 已修复（2026-08-26）**：`javbus_star.py` 的 `javbus_get()` 和 `javbus_magnet.py` 的 `_get_json()`（search_api 也走本地 javbus-api，同坑）均已改为 host-gated proxy——仅当目标 host 非 localhost/127.0.0.1/::1 时才带 PT_PROXY。验证：`javbus_star.py "浅野こころ"` 49 部全返回 EXIT=0；`javbus_magnet.py SNOS-151 --api http://localhost:8922` 正常。**修脚本时注意别只修 javbus_star.py——搜一下所有对 localhost 请求传 PT_PROXY 的地方。**
- 除上述两脚本外，其余 PT_PROXY 使用均合理：mteam_api/cross_seed/pt_download/sukebei_search/site_profile 的 PT_PROXY 都用于外网 PT 站；jf_query.py 访问 Jellyfin 未传 proxy（正常）。
- 现象联动：cron 追剧会连续多天 [SILENT] 且输出无验证摘要——javbus-api 片单拿不到 → 走 PT 直搜回退 → 回退也没新货 → 静默。**用户问「为什么不汇报了」时，[SILENT] 不能当作「确实没新货」的证据，必须先验数据源健康**（见下节）。

**✅ Parallel PT search IS safe**: Unlike javbus-api calls, `pt_search.py` uses per-site connections (each via its own network path), not a single bottleneck proxy. 4 parallel `pt_search.py` calls for 4 actors completed successfully in ~60 seconds without errors (verified 2026-07-14). This is the recommended pattern for cron batch searches.

```bash
# ✅ DO: Parallel PT search (each call has independent network paths, no bottleneck)
python3 scripts/pt_search.py "ACTOR1" --adult --limit 10 > /tmp/pt_1.json 2>&1 &
python3 scripts/pt_search.py "ACTOR2" --adult --limit 10 > /tmp/pt_2.json 2>&1 &
python3 scripts/pt_search.py "ACTOR3" --adult --limit 10 > /tmp/pt_3.json 2>&1 &
python3 scripts/pt_search.py "ACTOR4" --adult --limit 10 > /tmp/pt_4.json 2>&1 &
wait  # all complete in ~60s
```

**⚠️ Hermes terminal 会拦截前台命令里的 `&`（2026-08-21 实测）**：cron 环境下单条前台 terminal 命令含 `&`+`wait` 会被拒绝（`Foreground command uses '&' backgrounding. Use terminal(background=true)`）。改用**单命令 `;` 顺序串联**（5 演员约 60-90s，实测全部 exit=0），或 terminal(background=true) 跑并行脚本。不要为并行再耗一次被拦截的调用。
# ❌ DON'T: Parallel javbus_star.py calls (all go through PT_PROXY → 502)
python3 scripts/javbus_star.py "ACTOR1" &  # proxy bottleneck
python3 scripts/javbus_star.py "ACTOR2" &  # all 502
```

**Correct cron pattern for javbus-api** (sequential direct curl, no proxy):
```bash
# ✅ DO: Sequential direct curl (no proxy for localhost)
curl -s -m 15 "http://localhost:8922/api/movies/search?keyword=ACTOR1&page=1" -o /tmp/jb_1.json
curl -s -m 15 "http://localhost:8922/api/movies/search?keyword=ACTOR2&page=1" -o /tmp/jb_2.json
curl -s -m 15 "http://localhost:8922/api/movies/search?keyword=ACTOR3&page=1" -o /tmp/jb_3.json
curl -s -m 15 "http://localhost:8922/api/movies/search?keyword=ACTOR4&page=1" -o /tmp/jb_4.json

# ❌ DON'T: Parallel javbus_star.py calls (all go through PT_PROXY → 502)
python3 scripts/javbus_star.py "ACTOR1" &  # proxy bottleneck
python3 scripts/javbus_star.py "ACTOR2" &  # all 502
```

After collecting raw API JSON, use a batch processing script (see Batch JF Dedup Queries in [cron-batch-patterns.md](cron-batch-patterns.md)) to handle JF dedup and filtering in one pass.

## javbus-api canary 假阳性：金丝雀通过 ≠ 后续查询成功

**已验证案例（2026-07-02）**：金丝雀测试用「三上悠亜」返回正常（30条），但紧接着查询「浅野こころ」「東雲みれい」「滝本雫葉」「楓ふうあ」全部 502。容器没有重启，金丝雀和实际查询间隔不到 10 秒。

**原因猜测**：javbus-api 可能对某些查询路径有内部缓存，金丝雀用的热门演员（三上悠亜）命中缓存但其他演员的查询要走实际抓取路径，而实际抓取路径已挂。

**对策**：
- 金丝雀只是一个粗略的存活信号，不能替代实际查询的重试策略
- 金丝雀通过 + 后续全 502 → 立刻回退 PT 直搜，不要逐个重试（浪费时间）
- 不要在 cron 中尝试 `sudo docker restart javbus-api`（cron 模式会被审批拦截）
- 若后续有机会（非 cron 环境），优先 `docker restart javbus-api && sleep 4` 再试

### javbus-api 404 "Not Found" JSON 错误响应体

当容器完全宕机或 API 路由不可达时，返回一个紧凑的 35 字节 JSON 错误（非标准 HTML 404 页面）：

```json
{"error":"Not Found","messages":[]}
```

这不同于 502 代理瓶颈（产生 HTML 或空 body）。金丝雀测试返回此形状 → **容器宕机**，立即跳过所有 javbus-api 查询，全走 PT 直搜 + JF 去重。不要逐个演员重试——全部会以相同方式失败。

**已验证案例（2026-07-24）**：金丝雀 `curl localhost:8922/api/movies/search?keyword=三上悠亜` 返回 `{"error":"Not Found","messages":[]}`（35 字节）。确认容器宕机后直接跳过 javbus-api，4 演员 PT 并行搜索 + JF 两阶段去重全程 ~3 分钟完成。

### javbus-api 空响应（0 字节，exit 0）

容器可能返回空 body（0 字节）且 exit code 0，无任何错误信息。这不同于 502（HTTP 错误码）或 404 JSON（`{"error":"Not Found"}`），而是**服务端口开放但不返回任何内容**——容器内部进程可能已僵死但端口仍在 listen。

**已验证案例（2026-07-26）**：金丝雀 `curl -s -m 15 "http://localhost:8922/api/movies/search?keyword=三上悠亜&type=normal&page=1"` exit 0，但输出文件 0 字节完全为空。处理策略与 404/502 相同：**立即跳过 javbus-api，全走 PT 直搜回退**。

**三种 javbus-api 故障形态速查**：

| 故障形态 | curl exit | body | 含义 | 对策 |
|---------|-----------|------|------|------|
| 502 代理瓶颈 | 0 | HTML 或空 | 代理并发过载 | PT 直搜回退 |
| 404 JSON | 0 | `{"error":"Not Found","messages":[]}` | 容器宕机/路由不可达 | PT 直搜回退 |
| 空响应 | 0 | 0 字节空文件 | 进程僵死/端口空 listen | PT 直搜回退 |
| **Timeout awaiting 'request'** | 0 | `{"error":"Timeout awaiting 'request' for 5000ms","messages":[]}`（~63 字节） | 上游抓取超时（javbus.com 慢 / 容器内 HTTP_PROXY 抖动），容器本身活着 | **先重试 1-2 次**，常可恢复 |

前三种（502/404 JSON/空响应）处理策略一致：不重试，不走 javbus-api，全量 PT 直搜 + JF 去重。

**第四种「Timeout awaiting 'request' for 5000ms」是瞬时上游超时，与前三种不同**。已验证（2026-08-17）：金丝雀首查返回此错误（63 字节），`-m 25` 重试一次即恢复完整数据（7389 字节、30 条）。对策：遇到此错误先重试 1-2 次（`-m 25`），仍失败才按容器故障走 PT 直搜回退——不要当 502/404 直接放弃 javbus-api。

## PT/JF 番号前缀不匹配：先验证 title+date，别想当然（2026-08-11 修正）

PTTime/M-Team 搜索结果中的番号前缀可能与 JavBus/JF 中的实际前缀不同（S1 rebrand：SSIS↔SONE、SSNI↔SSIS）。**但前缀不同 ≠ 一定是同一部作品**——两码可能是完全不同的两部片：

**⚠️ 已验证反例（2026-08-11，推翻早期想当然判定）**：
| 码 | 作品 | 日期 |
|----|------|------|
| PTTime 标的 **SSIS-785** | 迫られると断れない美脚アナウンサー…逆おねだりビッチ！ 楓ふうあ | 2023-07-21 |
| JF 中的 **SONE-785** | 新人スポーツキャスターは局から人気スポーツ選手にあてがわれても断れず… 楓ふうあ | 2025-07-18 |

两部是**不同作品**。08-09 报告按「前缀混标→已拥有」误判 SSIS-785 已在 JF 而漏报，08-10 才纠正为 🆕 新资源。教训：**SSIS-785 逐码 JF 返回 0 时，不要因为「可能是 SONE-785 混标」就标已拥有——先用 javbus 查两个码，title+date 一致才合并视为同片；不一致则 PT 码是独立新资源**。

**对策（判定顺序）**：
1. JF 逐码验证返回 0 → 不要立即下结论「新资源」或「前缀混标」
2. 先用 javbus 分别查 PT 码和 JF 码（`curl -sG ... --data-urlencode "keyword=CODE"`），对比 title + date
3. title+date 一致 → 同一部片，以 JF 实际编号为准，标注「✅ 已拥有(JF: SONE-785)」
4. title/date 不一致 → PT 码是独立作品，JF 无 → 正常按 🆕 新资源展示

## PT actor search 不完整 / 完全失败：需要逐码搜索

PT 多站搜索 `pt_search.py "演员名" --adult --limit 10` 依赖种子标题中包含演员名。但以下情况会导致个别番号漏掉，甚至**完全返回 0 条**：

- **M-Team 英文标题**：种子标题为英文，不含日文演员名
- **PTTime 简略标题**：部分种子标题只含番号不含演员名（如 `SNOS-099` 而非 `SNOS-099 浅野こころ`）
- **--limit 截断**：搜索结果只取 top 10，可能截断匹配度较低但确实存在的条目
- **完全失败**：某些演员在所有站点的种子标题中均不出现，actor search 返回 0 条，但逐码搜索能全部命中

### 部分遗漏案例（2026-07-22）

| 演员 | PT actor search 结果 | 漏掉的番号 | 补充代码搜索发现 |
|------|---------------------|-----------|-----------------|
| 楓ふうあ | 10 个不同番号 | SONE-706 | M-Team **5 个版本**（6.1~19.8 GB，21~104 seeds） |

### 完全失败案例（2026-07-31）

| 演员 | PT actor search | 罗马字名 search | 逐码搜索结果 |
|------|----------------|---------------|-------------|
| 楓ふうあ | **0 条**（全站） | `Kaede Fuua` → **0 条** | 11 个番号逐码搜 PT **全部有结果**（SONE-982/760/706/591/403/308, SSIS-980/743/652/428/296），做种 41~713 |
| 滝本雫葉 | **0 条**（全站，简体名） | `Takimoto Shizuha` → **1 条**（ABF-330，已在 JF） | 4 个番号逐码搜 M-Team **全部有结果**（ABF-371/369/317/308），做种 30~126，标题均用繁体「瀧本雫葉」 |

说明：楓ふうあ在 M-Team 种子标题中从未以日文或罗马字名出现（标题只含番号+剧情简介），PTTime 同理。actor search 在所有配置站点上均返回 0，但逐代码搜索全部命中。

### 对策

- **PT actor search 返回 0 条 ≠ 无资源**。立即对 javbus 片单中所有不在 JF 的番号做逐码 PT 搜索
- PT actor search 返回 >0 条 → 对 javbus 片单中**未出现在 PT 结果里的最近 6 个月番号**做逐码补充搜索
- 逐码搜 PT：`python3 scripts/pt_search.py "CODE" --adult --limit 5`
- 优先搜 M-Team（API 快、做种多），其次 PTTime
- actor search 返回 0 时，可快速试一次繁体变体（滝→瀧）或罗马字名——可能命中个别作品（如 ABF-330），但**不能止步于此**：英文名/繁体回退可能只命中已拥有的旧作，最终必须对 javbus 片单中不在 JF 的番号逐码补搜才算完整（已验证 2026-08-06：英文名命中 ABF-330 已拥有，漏掉 4 部新作）

## PT 关键词搜索假阳性：子串匹配（2026-07-31 新增）

PT 搜索 `pt_search.py "演员名" --adult` 使用关键词匹配，可能匹配到名称包含目标字符串的其他演员：

| 搜索词 | 假阳性结果 | 实际演员 |
|--------|-----------|---------|
| `浅野こころ` | SONE-855, SONE-711, SSIS-959 | 歌野こころ、川越にこ |

`浅野こころ` 中 `こころ` 部分匹配了 `歌野こころ` 和 `川越にこ`。PT 搜索结果中标题不含「浅野」的条目需要交叉验证 javbus 片单——javbus 不收录的番号大概率是假阳性。

**追加案例（2026-08-16）— 短码假阳性可 100% 全中别的码**：搜索 `SS-072`（ETERNAL 写真）返回 4 条结果全部是 DASS-072/MRSS-072/FSDSS-072（M-Team）——目标码本身无独立种子。短码（2 字母前缀）极易命中同数字不同前缀的其他番号，`--limit 4` 时甚至可能全为假阳性。对策：逐条核对结果标题的**完整前缀**，标题不含目标前缀的条目不算「有种子」；全部假阳性 → 该码 PT 无种，写真类可直接跳过。

**对策**：
- PT actor search 结果中的每个番号，先在 javbus 片单中验证确属该演员
- 标题不含 actor 全名 → 高度怀疑假阳性
- 特别警惕带 `こころ`、`みれい`、`あい` 等常见名后缀的搜索词

## M-Team 预发布：PT 搜索结果不在 JavBus 上

M-Team 有时比 JavBus 更早收录新片。已验证案例（2026-07-21）：

- **SNOS-324**（楓ふうあ）：M-Team 已有 3 个版本（4.8~15.8 GB），但 JavBus `/api/movies/SNOS-324` 返回 404 "Not Found"

**对策**：
- PT 搜索结果中出现的番号在 JavBus 上 404 → 不是错误，是**预发布**，应标记为 `🆕 预发布` 正常展示
- 不要因为 JavBus 404 就排除该条目——PT 已经有种就是有效资源
- 同样不要因为「不在 javbus 片单中」就认为 JF 去重环节不需要查——仍需逐码 JF 验证

**⚠️ 预发布次日被 javbus 收录 → 候选数 +1 是幻影增量，不是新资源（2026-08-23 验证）**：昨日报告的 M-Team 预发布（如 SNOS-360，昨仅预发布交叉核对可见）今日被 javbus 收录后，会从「片单外」转入片单候选池，导致 raw/kept/not_downloaded/jf_notfound 各 +1（156→157、79→80）。这不是新资源。判定：只要 +1 的码恰好等于昨日预发布（昨报差集=0），本轮就是 [SILENT]，禁止把计数上涨当新资源报告。**昨报 backlog 重建时必须把最近一次实质报告的 🆕 预发布码并入集合**（08-23 的 80 码 backlog = 08-15/16 的 79 码 + 08-22 的 SNOS-360）。

## chase_crosscheck.py 静默空输出 = bug 不是「0 预发布」（2026-08-22 实测）

**已验证事故**：`chase_crosscheck.py` 从 `pt_<key>.json` 文件名提取 key 时用 `os.path.basename(f).split('_')[1]`，得到的是 `asano.json`（**带 .json 后缀**）而非 `asano`。导致它去找 `pt_asano.json.json`（不存在）→ `except: continue` 静默跳过所有演员，**整段输出为空、exit 0**——看起来像「0 预发布」，实则脚本啥也没干。08-22 追剧因脚本空输出，差点漏掉 SNOS-360（浅野こころ M-Team 预发布），靠手动重写 crosscheck 才抓到。

**根因**：`split('_')[1]` 没剥 `.json` 后缀。脚本 docstring 写「Verified 2026-08-20」是假象——那天很可能同样空输出被误读成 0 预发布。

**对策（铁律）**：
- **chase_crosscheck.py 输出为空 → 先怀疑脚本静默失败，不是「无预发布」**。空输出必须手动重跑 cross-check 验证（逐 key 打印 `== <key>: PT unique=N, 不在 javbus 片单: N`）
- 已修复：key 提取改为 `os.path.splitext(os.path.basename(f).split('_', 1)[1])[0]`（剥 .json、key 可含下划线）
- 手动 cross-check 兜底模式（脚本坏时）：逐 key 读 `pt_<key>.json` → 从 `results[].title` 用 `\b([A-Z]{2,6}[-_ ]?\d{2,5})\b` 提码 → 与 `jb_<key>_p*.json` 的 `movies[].id` 集合做差集 → 差集即预发布候选
- 预发布候选命中后**必须核实非子串假阳性**（标题是否真含该演员全名）——SNOS-360 标题末尾含「浅野こころ」才确认是真预发布，而非「こころ」误匹配别的演员（歌野こころ/川越にこ）
- 每个预发布候选还要过 JF 逐码 + download_history check（SNOS-360 两关都 0 才确认真新），发行日期/演员/导演用 `/torrent/detail` 端点补齐（见 mteam-api.md）

### ⚠️ crosscheck 的 PRE-RELEASE? 命中先过 NONSTD 前缀过滤，别当新资源（2026-08-27 实测）

`chase_crosscheck.py` 只做「PT 码 ∉ javbus 片单」差集，**不应用 NONSTD 过滤**——写真/VR 等非标准内容的码同样会被标成 `PRE-RELEASE?`。判定真实预发布前，先按 NONSTD 列表（REBD/REBDB/SIVR/MBDD/OFJE/IPOK/PFES/FWAY/IPVR/MBRBA/THN/THU/PPR/PPX/SS）过滤，命中即非标准内容，**不构成可报告的新资源**，本轮照常 [SILENT]，不要花时间逐个核实：

- 2026-08-27 实测：crosscheck 报 2 个 PRE-RELEASE?（REBD-1057 M-Team 楓ふうあ REbecca 写真、REBDB-883 PTTime 瀧本雫葉 写真）——两者均 NONSTD，追剧流水线 chase_extract 本来就会滤掉，报告判定为无新资源
- REBDB-883 自 08-11 起反复出现在 crosscheck 输出（javbus 未收录但 PT 有种），每轮都被 NONSTD 过滤跳过，属已知常驻噪音
- **PT 侧增量确认技巧**：把当日 `pt_<key>.json` 提取的番号集合与上一轮 `pt_<key>.json` 差集，`NEW in today` 只有 NONSTD 码（如 REBD-1057）→ 无真实新资源；有非 NONSTD 新码才进入预发布核实流程
- **javbus 分页计数 ≠ 唯一片单数**：分页求和可能比去重后多（2026-08-27 fuua 三页 30+30+11=71，去重后唯一 70，跨页重复 1 条；2026-08-28 三页 30+30+12=72 → 去重 70，跨页重复 2 条）。chase_extract.py 的 `seen` 集合已去重，跨日对比片单数量一律用去重后集合，别被分页计数吓到以为多了新番号
- **跨日对比看 CANDIDATES 不看 TOTAL（2026-08-28）**：chase_extract 输出 `TOTAL=211 CANDIDATES=157 FILTERED={'nonstd': 52, 'exclude_multi': 2}`，昨日为 `TOTAL=210 CANDIDATES=157 FILTERED={'nonstd': 51, ...}`——TOTAL 会随 nonstd 记录增减而漂移（多/少一条写真或 VR 记录就 ±1），但 CANDIDATES 稳定。判定「片单有没有变」只看 CANDIDATES 数与 FILTERED 分布，TOTAL ±1 是噪音，别当新番号报告，也别写进验证摘要造成误读

## _cron_javbus_check.py 超时问题

`_cron_javbus_check.py` 设计为单次调用完成所有演员的 javbus-api 查询 + JF 去重 + 下载历史过滤，但在 cron 环境实测中频繁超时（120s 无输出退出）。原因可能包括：
- javbus-api 容器对多演员连续查询的响应延迟累积
- 脚本内部 JF 逐码验证逻辑阻塞

**当前推荐 fallback（已验证稳定）**：回到手动顺序流程
```bash
# Step 1: 顺序直接 curl javbus-api（不走代理）
curl -s -m 15 "http://localhost:8922/api/movies/search?keyword=ACTOR1&type=normal&page=1" -o /tmp/jb_actor1.json
curl -s -m 15 "http://localhost:8922/api/movies/search?keyword=ACTOR2&type=normal&page=1" -o /tmp/jb_actor2.json
# ...

# Step 2: 从 javbus JSON 提取番号，与 JF Stage 1（演员名搜索）交叉对比
# Step 3: 对 Stage 1 漏掉的番号逐码 JF 验证（while read 循环）
# Step 4: download_history filter 最终过滤
# Step 5: PT 搜索仅对最终剩余番号
```
此流程在 2026-07-17 对 4 位演员的全量追剧中稳定完成（~3 分钟总耗时）。

## `source secrets.env` 在 cron 模式下可能失败

`secrets.env` 中某些值（如 `sl-session=flxUWxolWmqaBPSBZD69Yg==`）包含 shell 不识别的语法，`source secrets.env` 会报 `未找到命令` 并中断。所有 pt-claw 脚本内部通过 `_load_env_file()` 安全读取 `.env` 文件，无需手动 source。如需在 ad-hoc 命令中使用环境变量，用 `export $(grep -v '^#' secrets.env | xargs)` 替代 `source secrets.env`。

## JF name 字段番号提取方式

JF `jf_query.py --search "演员名"` 返回的 items 中，番号位于 `name` 字段开头（如 `"SNOS-002 我想拯救..."`），而非独立的 `FileName` 字段。提取番号的正则为 `^([A-Z]{2,6}[-_]?\d{2,5})`，从 `name` 字段 match group(1) 即可。

常见坑①：初次可能误从 `item['FileName']` 或 `item['SortName']` 提取，这些字段在 `--search` 返回中通常不存在或为空，导致提取结果全部为 0。

常见坑②：Python 解析时误用大写键名 `data["Items"]` / `item["Name"]`。`jf_query.py --search` 返回的实际 JSON 键名是**全小写** `data["items"]` / `item["name"]`。用 `Items`/`Name` 会静默返回空列表或 KeyError。

常见坑③：M-Team 预发布——PT 搜索返回的番号（如 SNOS-324）可能在 JavBus 上查不到（返回 404 "Not Found"），这不代表结果无效，而是 M-Team 比 JavBus 更早上架。应将其标记为 🆕 预发布并正常展示。

## Cron 批量 JF 查询的安全模式

Cron 环境禁止 `| python3 -c` 管道和 `execute_code`，批量 JF 查询用以下模式：

```bash
# ✅ 正确：shell for 循环逐条保存，最后用 python3 合并读取本地文件
cd /home/alex/.hermes/skills/media/pt-claw
for code in SSIS-578 SSIS-673 SONE-982; do
    python3 scripts/jf_query.py --search "$code" > /tmp/jf_$code.json 2>&1
done

# 合并读取（不触发管道拦截——python3 读的是本地文件）
python3 -c "
import json, glob
for f in sorted(glob.glob('/tmp/jf_*.json')):
    d = json.load(open(f))
    print(f.split('_')[1].replace('.json',''), d.get('total',0))
"
```

**禁止的做法**（cron 会拦截）：
```bash
# ❌ 管道接 python3 -c
echo 'SSIS-578' | python3 -c "import sys; ..."
# ❌ for 循环管道
for code in A B C; do ... | python3 -c "..."; done
# ❌ execute_code（cron 模式直接 blocked）
```

## javbus-api canary 假阴性：手工 URL 编码错误（2026-08-09）

金丝雀用手工 %-encoding 拼 keyword 时容易把字编错，返回**合法 JSON 但 movies=[]**——这不是 API 挂了：

| 情况 | 结果 |
|------|------|
| `keyword=%E4%B8%89%E4%B8%8A%E6%82%A0%E4%BA%9C`（三上悠亜，亜=E4BA9C） | 30 条 ✅ |
| `keyword=%E4%B8%89%E4%B8%8A%E6%82%A0%E7%94%9C`（错编成「三上悠甜」，甜=E7949C） | `{"movies":[],"pagination":{...}}`，exit 0 |

**判定顺序**：canary 返回 0 但 JSON 结构完整（有 `pagination` 字段）→ 先怀疑 keyword 编码，改用 `curl -sG ... --data-urlencode "keyword=..." --data-urlencode "type=normal"` 重跑一次。只有 `--data-urlencode` 也 0，或出现 404 JSON / 502 / 空 body，才按容器故障走 PT 直搜回退。

**铁律**：canary 和所有演员查询一律用 `-sG --data-urlencode`，禁止手工拼 %-encoding（中日文假名/汉字极易编错）。

## javbus-api 片单响应结构 & 分页（2026-08-09）

`/api/movies/search` 返回的每条 movie 字段是 `date / id / img / title / tags`：

- **番号在 `id` 字段**（`m['id']`），不存在 `code` 字段；从 `title` 正则提取也会漏（标题里番号不总在开头）。
- 分页：`pagination.hasNextPage` / `nextPage`，每页 30 条。热门演员片单超一页（楓ふうあ 70 部 = 3 页）。
- cron 安全翻页循环（逐页 curl 落盘，`hasNextPage` 为 False 即 break）：

```bash
for p in 2 3 4 5; do
  curl -sG -m 20 "http://localhost:8922/api/movies/search" --data-urlencode "keyword=$name" --data-urlencode "type=normal" --data-urlencode "page=$p" -o "/tmp/jb_${key}_p${p}.json"
  hn=$(python3 -c "import json; d=json.load(open('/tmp/jb_${key}_p${p}.json')); print(len(d.get('movies',[])), d.get('pagination',{}).get('hasNextPage'))")
  case "$hn" in *True*) continue;; *) break;; esac
done
```

## 全片单逐码补搜 vs 6 个月规则（2026-08-09）

已验证（瀧本雫葉）：actor search 只命中部分（PTTime ABF-056~197 + M-Team ABF-340/350/354/369/371），按「最近 6 个月」规则补搜会漏掉**大量有 M-Team 种子的旧作**。本次把 javbus 片单中所有不在 JF 的番号全量逐码搜 PT，额外发现 **17 部**：ABF-317/308/297/284/276/264/257/240/235/219/206/177/171/096/067 + GNI-002（出道作）+ DLV-003，全部 M-Team 50% promo。

**结论**：对「希望收全片单」的演员，全量逐码补搜（不限 6 个月）才是完备做法；6 个月规则只是控制 API 调用量的快速模式。逐码搜到种子后仍要逐码 JF 验证。

**附带数据点**：ABF-127 演员名搜索（雫葉）未命中，但逐码 JF 验证 total=1 —— 又一个 Stage-1 假阴性案例，两阶段去重不可省。

### 「已全收录」结论也会过期：浅野こころ OAE-287（2026-08-13）

**已验证事故**：浅野こころ 在 08-09 和 08-11 连续两轮被报「✅ 已全收录」，但 08-13 对 javbus 片单中不在 JF 的剩余番号做逐码 PT 补搜时，发现 **OAE-287**（2025-04-18，M-Team 5.7~18.4GB，13~33 seeds）从未出现在任何 actor search 结果里（`--limit 10` 截断 + 标题不含演员名），是全新资源。

**根因**：actor search 只返回 top-N，且该片标题不带演员名 → 多轮「已全收录」都是基于**不完备搜索**的误判。

**对策**：
- **「已全收录」只对「javbus 片单全部逐码验证过」的演员成立**；只靠 actor search + JF 初筛就写「已全收录」是虚假信息（同 08-13 捏造「已入库」一类问题）
- 对声明过「已全收录」的演员，仍要周期性对 javbus 片单中不在 JF 的番号做逐码 PT 补搜——新上架/漏网作品随时可能冒出来
- 逐码补搜时同样要逐码 JF 验证（OAE-287 逐码 JF=0 才确认是真新，SONE-208/855 等逐码 JF=1 被排除）

## 全量逐码补搜批量高效模式 + 08-15 实证：楓ふうあ/愛才りあ 漏报 13 部（2026-08-15）

**已验证事故**：08-11/08-13 连续报告 楓ふうあ「JF 14，未收录 5」、愛才りあ「JF 9，未收录 8」，但 08-15 全片单逐码补搜发现实际 **楓ふうあ有 40 部未入库**、**愛才りあ有 12 部未入库**——「未收录 5/8」严重低估。逐码 PT 补搜后确认 **13 部为从未报告过的真新资源**：愛才りあ 4 部（IPZZ-749/663/565/520，2025 年）、楓ふうあ 9 部（SONE-591/403/308/263/114/196/067、JUQ-589、SSIS-825，2023-2024 年）。

**根因**：actor search 只返回 top-N + 标题不含演员名 → 漏掉中间年份作品；「6 个月规则」又把 2024 及更早作品排除在外。多个连续报告把「actor search top-N 结果都已在库」误当成「已全收录」。

**对策（批量高效模式，cron 安全，08-15 已验证 ~3 分钟跑通 5 演员 157 候选番号）**：
1. 把 javbus 片单全部候选番号写进一个文件（`write_file` → `/tmp/jbcheck/codes.txt`），排除 SIVR/REBD/REBDB/MBDD/OFJE/IPOK/PFES/FWAY/MBRBA/IPVR/THN/THU/PPR/PPX 等非标准前缀
2. `python3 scripts/download_history.py filter < codes.txt > not_downloaded.txt`（输出**不在**下载历史的番号，一步排除已下载）
3. 对 not_downloaded.txt 逐码 `python3 scripts/jf_query.py --check "CODE" > /tmp/jbcheck/jfc_CODE.json`——**用 `--check` 而非 `--search`**：`--check` 返回紧凑 `{code,found,count}` 单行 JSON（默认查 JF1 成人库），比 `--search` 逐条返回 items 列表快且省上下文
4. 聚合 jfc_*.json：`found=false` 的即「未入库未下载」候选
5. 对候选逐码 `python3 scripts/pt_search.py "CODE" --adult --limit 5` 确认 PT 有种 + 拿做种数——**每码约 5-10s，单次循环最多 ~10 码**，超过会 60s 超时，分批跑

此模式比「actor search + 6 个月规则」完备得多，且可复用：每次 cron 全量跑一遍即可兜住漏网作品，避免「已全收录」被连续多轮误报。

**⚠️ 批量模式只覆盖「javbus 片单里已有的码」，仍会漏掉 M-Team 预发布**（PT 已上架但 javbus 还没收录的新片，见「M-Team 预发布」节）。所以批量逐码补搜**不能替代步骤 2c 的 actor-name PT 搜索**：跑完批量模式后，仍要对每位演员做一次 `pt_search.py "演员名" --adult --limit 10`，交叉核对结果里有没有**不在 javbus 片单中的新码**（那些就是预发布/新上架）。2026-08-17 追剧先跳过了 actor search 直接走批量模式，事后才补跑 6 次 actor search 确认无预发布——两步都要做。

## 新番号可能已在下载历史：昨报清单 ≠ 下载权威清单（2026-08-16）

**已验证案例**：愛才りあ javbus 片单出现 IPZZ-918（2026-08-07 新番号），PT 逐码搜索 M-Team 83 seeds 有种子，且 08-15 报告的待确认/新发现列表都未提及 → 按「对比昨报」初步判为 🆕 新资源。但 `download_history.py filter` 已把它从候选里排除（not_downloaded.txt 无此码）——`download_history.py check --code IPZZ-918` 返回 `{"exists": true}`，实际 **08-09 已从 mteam 下载完成**。

**根因**：上一轮报告的资源清单（待确认/新发现）≠ 已下载的权威清单。报告可能因各种原因（actor search top-N 截断、标题不含演员名、下载渠道不同、报告分类遗漏）漏列某部已下载作品。

**对策（铁律）**：
- 对比昨报做「新/昨报」分类时，以 **download_history filter 后的候选清单**为准，不要以报告文本为准——被 filter 排除的码一律不是新资源
- javbus 片单/PT 搜索中出现、但不在候选列表的码（尤其新番号），展示前用 `python3 scripts/download_history.py check --code <CODE>` 快速确认状态，禁止仅凭「昨报没列」就当作新资源展示
- check 返回 exists=true 时，报告里如实标注「已下载」（如 IPZZ-918 已于 08-09 下载完成），不要混入可下载列表

## 追剧 cron 静默排查：数据源健康三连验（2026-08-25）

**触发场景**：用户问「每日追剧怎么不汇报了」。cron `last_status=ok` 且最近输出全是 `[SILENT]` **不等于一切正常**——可能是没新货（正常），也可能是数据源坏了（cron 拿不到片单，回退后无新货，照样静默）。必须按序验证：

1. **`cronjob action=list`** 确认任务没停、`last_status` 非 error。
2. **读最近输出** `~/.hermes/cron/output/<job_id>/` 最新 3-5 个文件：有详细验证摘要（canary 通过 + 片单数量 + diff=0）→ 静默是「真无新货」；输出只有孤零零的 `[SILENT]` 无摘要 → **可能数据源坏了，需实测验证**。⚠️ 别单凭摘要有无下结论：严格按输出模板规则 #5 执行时，无新资源轮次本来就该输出裸 `[SILENT]`（cron prompt 明令「不要多说一个字」）——08-24/25/26 三天均为裸 `[SILENT]`，08-26 实测数据源全健康（canary 30 条、210→157→124→80 与 08-23 完全一致、80 码差集=0）。「无摘要」只是失去事后判读依据，健康与否必须按下方三连验实测。
3. **数据源健康三连验**（绕开坏脚本，只读）：
   - 金丝雀：`python3 scripts/javbus_star.py "三上悠亜"` → 报 `HTTP 502 fetching http://localhost:8922/...` = 代理误套，不是容器挂（见上节定因诊断）
   - 代理对比：`curl -x <PT_PROXY> localhost:8922` vs 直连 → 502/200 即实锤
   - 片单对比：curl 直连分页拉 5 演员片单数，与上一份有摘要的报告对比（浅野49/東雲17/瀧本43/楓70/愛才31）——数量一致 + 最新日期未变 = 无新番号，静默属实
4. **PT 侧兜底验证**：`pt_search.py "演员名" --adult --limit 5` 查有没有 javbus 片单外的 M-Team 预发布。
5. 结论分两半给用户：① 为什么静默（数据源 502 + 确实无新货）② 积压待确认清单仍挂着（用户没回「下 X」的候选不会消失，提醒一下）。

**经验**：javbus-api 是追剧的片单数据源，它坏了的特征是「金丝雀 0 + 脚本报 502 + 直连 curl 200」。cron 静默时先怀疑数据源而不是「世界太平」，尤其当 [SILENT] 输出没有验证摘要时。
