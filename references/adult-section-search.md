# 成人区（9kg）搜索适配

## PTTime

- **页面**: `https://www.pttime.org/adults.php`
- **搜索参数**:
  - **按标题**: `searchstr=` — 匹配种子标题文本
  - **按演员**: `actor=` — 匹配演员标签（演员名以 tag 形式存在于 HTML 中，不在标题里，必须用 `actor=` 才能命中）
- **URL 格式**: `https://www.pttime.org/adults.php?searchstr=<关键词>` 或 `adults.php?actor=<演员名>`
- **HTML 结构**: 与主页 `torrents.php` 相同（NexusPHP 双行结构），解析器通用
- **下载链接**: 与主页格式一致 `download.php?id=XXX&passkey=YYY&uid=ZZZ`
- **演员标签格式**: `<a class='dib cp' href='/adults.php?actor=演员名'><span class='tags'>演员名</span></a>`
- **网络**: 直连 SSL 握手可能超时，建议走代理

### 搜索模式对比

| 搜索类型 | 参数 | 命中范围 | 示例 |
|---------|------|---------|------|
| 按番号 | `searchstr=SSIS-448` | 标题含 SSIS-448 | 精确匹配番号 |
| 按演员 | `actor=浅野心` | 所有该演员作品 | 按标签过滤，命中率高 |
| 按关键词 | `searchstr=4K` | 标题含 4K | 宽泛匹配，噪音大 |

**重要**: 搜索演员不能用 `searchstr=`（演员名通常在 tag 里不在标题里），必须用 `actor=`。

### URL 编码

中文参数必须 URL 编码。curl 示例：
```bash
curl -s --data-urlencode "actor=浅野心" "https://www.pttime.org/adults.php" -G -b "cookie_str"
```

### pt-claw 适配状态

**已适配**。`pt_search.py` 中 `search_site()` 函数已处理 PTTime 成人区：
- `adult=True` 时切换到 `/adults.php?searchstr=`
- `actor` 参数时切换到 `/adults.php?actor=`
- HTML 解析器与普通搜索共用（NexusPHP 结构一致）

### PT-depiler 对比

PT-depiler 对 PTTime 成人区的处理方式：
- 成人区入口：`/adults.php`（与我们一致）
- 通过 `searchEntry.area_special` 预设，默认禁用
- 使用 `#url` 特殊 key 直接替换请求 URL
- 成人分类 ID（PTTime 独有，与 M-Team 不同）:

| Category ID | 名称 |
|-------------|------|
| 440 | 9kg-步兵(步兵/无码) |
| 441 | 9kg-骑兵(骑兵/有码) |
| 442 | 9kg-III(三级片、限制级电影) |
| 443 | 9kg-H漫(动漫、漫画) |
| 444 | 9kg-H游(游戏及相关) |
| 445 | 9kg-H书(书籍、有声书) |
| 446 | 9kg-H图(写真、图片、私拍、短视频) |
| 447 | 9kg-H音(ASMR、音频、音乐) |
| 448 | 9kg-H综(综艺、综合、剪辑、其他等) |
| 449 | 9kg-H同(男同、女同、人妖) |

## M-Team (馒头)

- **Web 页面**: `https://kp.m-team.cc/browse/adult`（需 Cookie，但 M-Team 禁止 Cookie 访问 API）
- **API 搜索**: ✅ 已验证 `mode: "adult"` 参数有效
- **API 限速**: 1000 次/24h，超限返回 403

### 已验证的 API 方案

```python
POST https://api.m-team.cc/api/torrent/search
Headers: x-api-key, Content-Type: application/json
Body: {"keyword": "", "page": 1, "size": 25, "mode": "adult"}
```

详细验证结果见 `references/mteam-api.md`「成人内容 / 9kg 区搜索」章节。

### 三方项目成人搜索对比

| 项目 | 成人搜索方式 | 实现状态 |
|------|------------|---------|
| **pt-claw** | 未实现 | 待开发 |
| **PT-depiler** | `mode: "adult"` in JSON body，通过 `searchEntry.area_adult` 预设（默认禁用） | 完整实现 |
| **MoviePilot** | `visible: 1`（仅过滤活种，非成人区切换）；实际成人搜索依赖站点 URL 而非 API 参数 | 部分实现 |

## PTSkit（拾刻）

- **URL**: https://www.ptskit.org/
- **框架**: NexusPHP
- **标签**: 短剧、成人
- **成人区**: `/special.php`（称为「十八禁」）
- **成人分类**:

| Category ID | 名称 |
|-------------|------|
| 412 | 欧美 |
| 411 | 日本 |
| 410 | 国产 |

- **成人区入口**: `searchEntry.area_9kg`，URL 为 `/special.php`（PT-depiler 默认禁用）
- **搜索参数**: 与综合区相同（NexusPHP 标准 `search` 参数），HTML 结构一致
- **pt-claw 适配状态**: 未适配

## PTHome（铂金家）

- **URL**: https://pthome.net/
- **框架**: NexusPHP
- **标签**: 影视、综合
- **成人区**: **无**（PT-depiler 定义中无成人区入口）
- **分类**: Movies(401)、TV Series(402)、TV Shows(403)、Documentaries(404)、Animations(405)、Music Videos(406)、Sports(407)、HQ Audio(408)、Games(410)、Study(411)、Others(409)
- **pt-claw 适配状态**: 未适配
