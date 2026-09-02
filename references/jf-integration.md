# Jellyfin 集成 — 连接配置、去重与追剧

> ⚠️ **非必选项**。未配置 Jellyfin 时跳过去重检查，PT 下载功能完全不受影响。

## 连接配置

**认证方式**：Header `X-MediaBrowser-Token: <api_key>`（存 `secrets.env`）

**核心端点**：

| 端点 | 用途 |
|------|------|
| `GET /Library/VirtualFolders` | 列出所有媒体库 |
| `GET /Items?searchTerm=xxx` | 搜索片库 |
| `GET /Items?parentId=xxx&recursive=true` | 浏览指定媒体库 |
| `GET /Persons/{name}` | 查演员信息 |
| `GET /System/Info` | 服务信息 |

**配置**：地址和 API key 存 `secrets.env`（`JELLYFIN1_URL`/`JELLYFIN1_API_KEY`），支持多个实例（JF1=影视、JF2=成人等）。实例用途映射写在 `user-preferences.md`。

## 重复检测逻辑

**推送前必须逐条查 Jellyfin（如果已配置），不能批量跳过。** 同一部剧的不同集要分别检查：

**匹配策略**（Jellyfin 未配置则全部跳过）：
- 🎬 **电影**：按标题+年份匹配，`TotalRecordCount > 0` 即跳过
- 📺 **剧集**：查到该剧后，获取已有 Season/Episode 列表，只下载缺失的集
- 🔞 **番号**：成人 Jellyfin 按番号精确匹配
- 👤 **主流演员/导演**：影视 Jellyfin 查该人作品
- 👤 **成人演员**：成人 Jellyfin 查该人作品（需和用户确认是主流还是成人演员）

**时间戳比对**：JF `DateCreated` vs qB `added_on`。JF 晚于 qB = 正常入库，不是重复。

## 关注列表

存储文件：`pt_wishlist.json`

```json
{
  "movies": [{"title": "流浪地球3", "year": 2027, "quality": "4K", "codec": "HEVC"}],
  "actors": [{"name": "Christopher Nolan", "type": "director"}],
  "fanhao": [{"code": "SSIS-448"}]
}
```

**操作**：「关注X」→ 加列表 / 「取消关注X」→ 移除 / 「我的关注」→ 展示全部

**厂牌排除**：`"exclude_prefixes": ["FNS"]` — 用户说「XXX厂牌不要」立即更新。

## 每日自动追剧

Cron 定义见 [first-time-setup.md](first-time-setup.md)。以下是追剧流程：

**⚠️ Cron 只搜索+去重+展示，不自动推送。**

1. 读取 wishlist → 下载历史 → JF 去重 → 搜索 → 筛选 → **展示结果**
2. 展示格式同确认闸门（站点、大小、做种、路径、元数据）
3. 用户确认后逐部推送

## 下载完成 → 自动刷新媒体库

`_cron_check.py`（下载进度检查 cron，每小时）检测到「新完成种子」时，自动对所有已配置的 JF 实例触发全库刷新（`POST {url}/Library/Refresh?api_key={key}` → 204），JF 扫描到新文件后自动抓取元数据（海报/简介/演员标签），无需手动刷新。

**内置保护（脚本已实现，见 `_cron_check.py` 的 `_jellyfin_refresh()`）**：
- **双实例遍历**：按序号检查 `JELLYFIN{N}_URL`/`JELLYFIN{N}_API_KEY`（N=1,2,…，取不到即停），配置了才刷；单实例失败仅 log.warning，不阻断其他实例和主流程。实例分工（JF1=成人、JF2=影视等）记录在 `user-preferences.md`「Jellyfin 集成」节——**用户配置与 skill 机制分开放**
- **限频**：最多每 30 分钟触发一轮（`JF_REFRESH_MIN_INTERVAL_MINUTES` 可用环境变量覆盖，默认 30），时间戳存独立状态文件 `pt_jf_refresh_state.json`（原子写 .tmp+os.replace，损坏按无状态处理）；两个实例共享一个限频窗口；只要发起过一轮刷新（≥1 实例）就写时间戳，失败的下一轮再试，避免半小时内反复重试打爆服务器
- **刷流目录跳过**：`save_path` 以 `JF_REFRESH_SKIP_PATHS`（逗号分隔，默认 `/downloads`）中任一**前缀**开头（大小写敏感，`startswith`）或 tags 含 PUBLIC_TAGS（sukebei/javbus）的新完成种子不触发；新完成种子全部被过滤 → 完全不刷新、不消耗限频窗口
- **总开关**：环境变量 `JF_REFRESH_ENABLED=0` 可整体禁用（默认启用）
- **内网直连**：`ProxyHandler({})` 空 opener——即使环境误带全局代理变量，JF 请求也绝不走代理（JF 是内网服务）
- **失败静默**：刷新结果并入脚本 JSON 输出的 `jf_refresh` 字段（triggered/skipped/servers 各状态码），失败只写 log（排障 `grep "jf refresh" logs/pt-claw.log`），不影响完成/死种通知

## 演员片库统计

回答「片库有哪些明星」「谁的最多」类问题。

**端点**：`GET /Items?parentId=<lib_id>&recursive=true&includeItemTypes=Movie&fields=People&startIndex=0&limit=200`

**关键点**：
- `fields=People` 必须传，否则 People 数组为空
- 分页：每次约 200 条，通过 `startIndex` + `TotalRecordCount` 翻页
- 同一演员可能出现多个名字（日文名 vs 中文译名）
- JF 响应不含演员 Id，只能按 Name 字符串匹配

## 常用命令速查

```bash
# 查看片库
curl -s "http://<host>:8096/Library/VirtualFolders" -H "X-MediaBrowser-Token: <key>"

# 搜索电影
curl -s "http://<host>:8096/Items?searchTerm=流浪地球&includeItemTypes=Movie" \
  -H "X-MediaBrowser-Token: <key>" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['TotalRecordCount'])"

# 查看演员作品
curl -s "http://<host>:8096/Persons?searchTerm=诺兰" -H "X-MediaBrowser-Token: <key>"
```
