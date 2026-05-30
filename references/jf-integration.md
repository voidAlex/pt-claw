# Jellyfin Integration + javbus-api — 片库感知与追剧

## Jellyfin 集成 — 片库感知 & 自动追剧（可选）

> ⚠️ **非必选项**。未配置 Jellyfin 时，跳过去重检查，PT 下载功能完全不受影响。用户在 Step 0 被询问是否配置。

### 概述

如果用户配置了 Jellyfin，通过 API 读片库实现去重和自动追剧。

### 备选下载源（成人内容）

当 PT 站做种不足（<3）时，自动回退到公开源。三个公开源互为补充：

## javbus-api — 影片元数据 API（可选）

> ⚠️ **非必选项**。不部署也能通过裸爬方式获取磁链、封面和预览图。部署后数据更结构化，磁链可排序，封面预览一键获取。用户在 Step 0 被询问是否部署。

| 源 | 类型 | 接入方式 | 做种数 | 封面 | 预览图 | 备注 |
|----|------|---------|--------|------|--------|------|
| **javbus-api** | REST API | Docker 自部署 (localhost:8922) | ❌ 无 | ✅ | ✅ | **首选**，磁链多+有去码/AI版 |
| **Sukebei Nyaa** | RSS 磁链 | `?page=rss&q=<番号>` | ✅ 有 | ❌ | ❌ | 备选，有种数可判断活性 |
| **JavBus 裸爬** | HTML+Ajax | 两步（详情页+Ajax） | ❌ 无 | ✅ | ✅ | javbus-api 不可用时的备选

**优先级**：JavBus（javbus-api，磁链多+去码/AI版）→ Sukebei Nyaa（有种数）→ JavBus 裸爬（最后手段）

---

#### Sukebei Nyaa（备选）

**直接用脚本**：`python3 scripts/sukebei_search.py <CODE> --limit 10`，返回 JSON（seeders/leechers/size/magnet/score）。不要手动 HTML 解析——脚本已处理 RSS、去重、广告过滤、评分排序。
```xml
<item>
  <title>SNOS-151 [自提征用]...</title>
  <link>https://sukebei.nyaa.si/download/4581362.torrent</link>
  <nyaa:seeders>1</nyaa:seeders>
  <nyaa:leechers>10</nyaa:leechers>
  <nyaa:infoHash>285382bc8b54d3c28c71d9a3158bb955b0cde017</nyaa:infoHash>
  <nyaa:size>6.3 GiB</nyaa:size>
</item>
```

**公开源搜索链路**（成人内容，PT做种不足时触发）：

1. PT 站搜到番号 → 做种低于阈值则标记为「低种」，触发回退
2. **第一轮 — JavBus（javbus-api）**：`GET /api/magnets/{番号}?gid=X&uc=Y`，获取结构化磁链（含大小/HD/字幕/去码标记），优先挑去码(uncensored/破解)/AI增强版本
3. **第二轮 — Sukebei Nyaa**（有种数可判断活性）：`python3 scripts/sukebei_search.py <番号> --limit 5`
4. 两源结果合并，按用户偏好排序（去码 > AI增强 > 做种数 > 字幕 > 画质）
5. 通过 `magnet:?xt=urn:btih:<hash>` 推 qBittorrent，标签 `javbus` 或 `sukebei`


#### JavBus（备选，量大无种数 + 封面/预览图）

JavBus 不提供做种数，但磁链数量是 Sukebei 的 2-3 倍，还能获取封面和内容预览截图。适合 Sukebei 也找不到种时碰运气。

**参考项目**：[ovnrain/javbus-api](https://github.com/ovnrain/javbus-api) — TypeScript，封装了完整 JavBus 接口（影片详情/磁链/搜索/演员），可作为自部署 API 或参考其解析逻辑。

---

**方式一：自部署 javbus-api（推荐，功能最全）**

使用 skill 目录下的 docker compose 模板部署：

```bash
# 复制模板到部署目录，替换代理地址为 PT_PROXY 的值
cp templates/docker-compose.javbus-api.yml ~/javbus-api/docker-compose.yml
# 编辑 ~/javbus-api/docker-compose.yml，将 <PT_PROXY> 替换为实际代理地址（同 secrets.env 中 PT_PROXY 的值）
docker compose -f ~/javbus-api/docker-compose.yml up -d
```

部署后在 `secrets.env` 中设置 `JAVBUS_API_URL=http://localhost:8922`。

部署后可用 REST API：

| 端点 | 功能 | 返回 |
|------|------|------|
| `GET /api/movies/{番号}` | 影片详情 | 封面图、预览截图(≤20张)、演员、导演、标签、时长、gid、uc |
| `GET /api/magnets/{番号}?gid=X&uc=Y` | 磁链列表 | 结构化：hash、大小(bytes)、HD/字幕标记、日期，可按大小/日期排序 |
| `GET /api/movies/search?keyword=xxx` | 关键词搜索 | 番号+标题+封面+标签列表 |
| `GET /api/stars/{starId}` | 演员详情 | 演员名、作品列表、头像 |

**影片详情返回示例**（关键字段）：
```json
{
  "id": "SSIS-406",
  "title": "SSIS-406 才色兼備な女上司が...",
  "img": "https://www.javbus.com/pics/cover/8xnc_b.jpg",  // 封面大图
  "date": "2022-05-20",
  "videoLength": 120,
  "director": {"id": "hh", "name": "五右衛門"},
  "stars": [{"id": "2xi", "name": "葵つかさ"}],
  "genres": [{"id": "e", "name": "巨乳"}],
  "samples": [  // 内容预览截图（大图+缩略图）
    {"src": "https://pics.dmm.co.jp/.../ssis00406jp-1.jpg",
     "thumbnail": "https://www.javbus.com/pics/sample/8xnc_1.jpg"}
  ],
  "gid": "50217160940",
  "uc": "0"
}
```

**磁链返回示例**（结构化，可直接排序筛选）：
```json
[{
  "id": "17508BF5C17CBDF7C77E12DAAD1BDAB325116585",
  "link": "magnet:?xt=urn:btih:17508...&dn=SSNI-730-C",
  "isHD": true,
  "title": "SSNI-730-C",
  "size": "6.57GB",
  "numberSize": 7054483783,
  "shareDate": "2021-03-14",
  "hasSubtitle": true
}]
```

**磁链排序参数**：`sortBy`（`size`|`date`）+ `sortOrder`（`desc`|`asc`），如 `/api/magnets/<番号>?gid=X&uc=Y&sortBy=size&sortOrder=desc`

**演员详情端点**：`GET /api/stars/<starId>` — `starId` 从影片详情 `stars[].id` 获取，返回演员信息 + 作品列表

**最新影片端点**：
- `GET /api/movies?type=normal` — 有码最新
- `GET /api/movies?type=uncensored` — 无码最新

---

**方式二：裸爬 JavBus（无需部署，轻量）**

```bash
# Step 1: 获取影片详情（含封面 + 预览图 + gid）
curl -s "https://www.javbus.com/<CODE>" -x <proxy> | python3 -c "
import sys,re,json
t=sys.stdin.read()
# 封面
cover=re.search(r'class=\"bigImage\"[^>]*href=\"([^\"]+)\"', t)
# gid
gid=re.search(r'var gid = (\d+)', t)
# uc
uc=re.search(r'var uc = (\d+)', t)
# 预览图（sample images）
samples=re.findall(r'https://pics\.dmm\.co\.jp[^\"]+\.jpg', t)
info={'cover':cover.group(1) if cover else None,
      'gid':gid.group(1) if gid else None,
      'uc':uc.group(1) if uc else None,
      'samples':samples[:10]}
print(json.dumps(info,ensure_ascii=False))
"

# Step 2: 用 gid+uc 调 Ajax 拿磁链列表（同上）
curl -s "https://www.javbus.com/ajax/uncledatoolsbyajax.php?gid=<GID>&lang=zh&img=...&uc=<UC>" \
  -x <proxy> -H "Referer: https://www.javbus.com/<CODE>"

# Step 3: 提取磁链 + 去重（同一 hash 会出现多次）
python3 -c "
import sys,re,urllib.parse
seen=set()
for m in re.finditer(r'magnet:\?xt=urn:btih:([a-f0-9A-F]{40})(?:&dn=([^&\042\047]+))?', sys.stdin.read()):
    ih=m.group(1).upper()
    if ih not in seen:
        seen.add(ih)
        dn=urllib.parse.unquote(m.group(2) or '')
        print(f'magnet:?xt=urn:btih:{ih}&dn={dn}')
"
```

**JavBus vs javbus-api 对比**：

| 能力 | 裸爬 | javbus-api |
|------|------|------------|
| 磁链获取 | ✅ | ✅ |
| 结构化磁链（大小/HD/字幕） | ❌ 需额外解析 | ✅ 开箱即用 |
| 封面预览 | ✅ | ✅ |
| 内容预览截图 | ✅ 可获取 | ✅ 开箱 ≤20张 |
| 按大小/日期排序 | ❌ | ✅ |
| 演员作品列表 | ❌ 需额外页面 | ✅ `/api/stars/{id}` |
| 部署成本 | 无 | Docker 一行 |


**公开磁链筛选规则**（添加前必过）：

Sukebei/Nyaa 等公开站混杂大量广告、合集、预告片，添加前必须逐条筛选：

**🚫 必须排除的**：
- 标题含广告词：`加群` `QQ` `微信` `tg` `广告` `推广` `福利` `免费` `导航`
- 合集/大包：`合集` `大合集` `まとめ` `pack` `collection` `全作品`，只下单部
- 预告/宣传：`预告` `宣传片` `sample` `trailer` `预览`
- 标题是纯 hash 或乱码的
- 文件数量异常多（>5 个视频文件）的

**✅ 优先选**：
- 带明确标签的：`FHDC` `HD` `4K` `中文字幕` `H265` `HEVC`
- 有清晰番号 + 标题的
- 做种数 ≥ 1（0 种的除非是唯一版本，否则跳过）

**流程**：搜到 N 条 → 逐条过筛 → 只保留正经片源 → 展示给用户选 → 再添加

**公开磁链管理规则**（区别于 PT 私有种子，Sukebei + JavBus 都是公开源）：

| 规则 | PT 私有种子 | 公开磁链（Sukebei/JavBus） |
|------|-----------|-------------------|
| 做种 | **必须保种**，否则封号 | ❌ 下载完立即删种，保留文件 |
| 上传 | 正常做种上传 | 🚫 **禁止上传**，避免占带宽 |
| 完成处理 | 持续做种 | 自动停止+删除任务 |

**为什么公开磁链不做种**：公开 tracker 没有分享率要求，做种纯浪费上行带宽。PT 站有考核必须保种。

**公开磁链生命周期监控**：

公开磁链（sukebei/javbus 标签）完成后自动备份并移除（文件保留），由 `_cron_check.py`（每 15 分钟）统一处理：
- 已完成的公开磁链 → 自动备份到 `torrent_backups/` → 从 qB 移除（不删除文件）
- 安全防线：公开种占比超 20% 时跳过清理，单次最多清理 50 个
- 手动清理仍可用 `python3 scripts/qb_public_cleanup.py --check`

```bash
# 搜索 Sukebei Nyaa
curl -s "https://sukebei.nyaa.si/?page=rss&q=SNOS-151" \
  -x $PT_PROXY

# 从 RSS 提取 magnet
# magnet:?xt=urn:btih:<infoHash>&dn=<title>
```

### Jellyfin 连接

**⚠️ Jellyfin 未配置 → 跳过此节，不影响 PT 下载。**

**认证方式**：Header `X-MediaBrowser-Token: <api_key>`（存 `secrets.env`，从环境变量读取）

**核心端点**：

| 端点 | 用途 |
|------|------|
| `GET /Library/VirtualFolders` | 列出所有媒体库 |
| `GET /Items?searchTerm=xxx` | 搜索片库 |
| `GET /Items?parentId=xxx&recursive=true` | 浏览指定媒体库 |
| `GET /Persons/{name}` | 查演员信息 |
| `GET /System/Info` | 服务信息 |

**配置**：Jellyfin 地址和 API key 必须存入 `secrets.env`（如 `JELLYFIN1_API_KEY=xxx`、`JELLYFIN1_URL=<JF_ADULT_HOST>`），skill 脚本从环境变量读取。偏好文件 `user-preferences.md` 记录实例数量和用途映射。

### 关注列表

存储文件：`pt_wishlist.json`

```json
{
  "movies": [
    {"title": "流浪地球3", "year": 2027, "quality": "4K", "codec": "HEVC"},
    {"title": "碟中谍9", "year": null, "quality": null, "codec": null}
  ],
  "actors": [
    {"name": "诺兰", "type": "director"},
    {"name": "汤姆·克鲁斯", "type": "actor"},
    {"name": "浅野こころ", "type": "adult_actress", "exclude_prefixes": ["FNS"]}
  ],
  "fanhao": [
    {"code": "SSIS-448", "actress": null}
  ]
}
```

**操作**：
- 「关注《流浪地球3》」→ 加到 movies 列表
- 「关注诺兰的电影」→ 加到 actors（type=director）
- 「取消关注 SSIS-448」→ 从 fanhao 移除
- 「我的关注列表」→ 展示当前所有关注

### 每日自动追剧 Cron Job

> 📌 此任务在 Step 0「配置完成后自动初始化」中已自动创建。以下为详细参考。

**⚠️ Cron 遵守确认闸门规则：只搜索+去重+展示，不自动推送下载。**

创建 cron 每天运行一次：

```python
cronjob(action='create',
    name="PT自动追剧",
    schedule="0 10 * * *",  # 每天上午10点
    prompt="""自动追剧检查（只搜索展示，不自动下载）：
1. 读取 pt_wishlist.json 关注列表
2. **第一步：读 pt_downloaded.json 下载历史**，构建已下载集合
3. 对每个关注项搜索资源（影视→PT全站，成人→javbus-api片单+Sukebei）
4. **逐条三重去重**：
   - 🛡️ 先查下载历史：在 pt_downloaded.json 中 → 无条件跳过
   - 🎬 再查 Jellyfin：已存在则跳过
   - ⏱️ 最后比时间戳：JF 入库 < qB 添加 → 真重复，跳过
5. 检查演员的 exclude_prefixes（如有），跳过排除厂牌的作品
6. **展示结果给用户**（每部列出：站点、大小、做种数、路径、元数据）
7. **绝对不推送下载**——等用户确认。用户说「下」后才执行推送
8. 无新资源则报告「今日无新资源」""",
    skills=["pt-claw"],
    deliver="origin"
)
```

**Cron 执行流程**：

1. 读取 wishlist → 下载历史 → JF 去重 → 搜索 → 筛选 → **展示结果**
2. 展示格式同 Step 4 确认闸门的格式（站点、大小、做种、路径、元数据）
3. 结尾加「回复「下」或「下第N个」确认下载」
4. 用户确认后，**在同一次对话中**逐部推送到 qBittorrent

### 重复检测逻辑（逐条/逐集检查）

**推送前必须逐条查 Jellyfin（如果已配置），不能批量跳过。** 同一部剧的不同集要分别检查：

```bash
# 剧集 — 查影视 Jellyfin 是否已有该季该集
curl -s "http://<jf_host>:8096/Items?searchTerm=<剧名>&includeItemTypes=Series&recursive=true" \
  -H "X-MediaBrowser-Token: <api_key>" | python3 -c "
import sys,json; items=json.load(sys.stdin)['Items']
...
"

# 电影 — 查影视 Jellyfin
curl -s "http://<jf_host>:8096/Items?searchTerm=<片名>&includeItemTypes=Movie&recursive=true" \
  -H "X-MediaBrowser-Token: <api_key>" | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(f'已存在 {d[\"TotalRecordCount\"]} 部')
"

# 番号 — 查成人 Jellyfin
curl -s "http://<jf_adult_host>:8096/Items?searchTerm=<番号>&recursive=true" \
  -H "X-MediaBrowser-Token: <api_key>" | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(f'片库已存在 {d[\"TotalRecordCount\"]} 部')
"
```

**匹配策略**（Jellyfin 未配置则全部跳过）：
- 🎬 **电影**：按标题+年份匹配，`TotalRecordCount > 0` 即跳过
- 📺 **剧集**：查到该剧后，获取已有 Season/Episode 列表，只下载缺失的集
- 🔞 **番号**：成人 Jellyfin 按番号精确匹配
- 👤 **主流演员/导演**：影视 Jellyfin 查该人作品
- 👤 **成人演员**：成人 Jellyfin 查该人作品。**关注时需和用户确认是主流还是成人演员**，不可猜错

### 演员片库统计

回答「片库有哪些明星」「谁的最多」类问题。

**端点**：`GET /Items?parentId=<library_id>&recursive=true&includeItemTypes=Movie&fields=People&startIndex=0&limit=200`

**关键点**：
- `fields=People` 必须传，否则 `People` 数组为空
- 分页：JF 每次最多约 200 条，通过 `startIndex` + `TotalRecordCount` 翻页
- 700+ 部影片约需 4 次请求
- 同一演员可能出现多个名字（日文名 vs 中文译名），如「桃乃木香奈」和「桃乃木かな」是同一人
- JF 响应不含演员的 `Id`，只能按 `Name` 字符串匹配
- `parentId` 需先通过 `/Library/VirtualFolders` 获取

```python
import urllib.request, json
from collections import Counter

star_count = Counter()
start = 0
limit = 200
while True:
    url = f"{jf_url}/Items?parentId={lib_id}&recursive=true&includeItemTypes=Movie&fields=People&startIndex={start}&limit={limit}"
    req = urllib.request.Request(url, headers={"X-MediaBrowser-Token": jf_key})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    items = data.get("Items", [])
    if not items:
        break
    for item in items:
        for p in item.get("People", []):
            if p.get("Type") == "Actor":
                star_count[p["Name"]] += 1
    start += limit
    if start >= data.get("TotalRecordCount", 0):
        break

# Top N
for name, cnt in star_count.most_common(20):
    print(f"{cnt}部 | {name}")
```

### 常用命令速查

```bash
# 查看 Jellyfin 片库
curl -s "http://<host>:8096/Library/VirtualFolders" -H "X-MediaBrowser-Token: <key>"

# 搜索是否存在某部电影
curl -s "http://<host>:8096/Items?searchTerm=流浪地球&includeItemTypes=Movie" \
  -H "X-MediaBrowser-Token: <key>" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['TotalRecordCount'])"

# 查看演员作品
curl -s "http://<host>:8096/Persons?searchTerm=诺兰" -H "X-MediaBrowser-Token: <key>"
```
