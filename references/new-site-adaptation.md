# New Site Adaptation — 新增 PT 站适配流程

## 新增 PT 站适配流程

当用户添加不在已适配列表中的 PT 站时，按以下步骤逐一适配，**每步完成后向用户确认再继续**。

### Step A：信息收集

向用户获取以下信息：

1. **站点 URL**（如 `https://hdtime.org`）
2. **站点是否需代理**：直接 curl 首页，连接超时/被墙 → 在 SITES 字典中设 `"needs_proxy": true`
3. **是否有成人区**：问用户「这站有成人区吗？」→ 有则 `new_site.has_adult = true`
4. **认证方式**：
   - 优先问用户有没有 API Key（站内 控制面板 → API Token）
   - 没有 API → 用 Cookie。让用户从浏览器导出或提供 Cookie 字符串

Cookie 存入 `secrets.env`：`PT_COOKIE_<SITE>`（站点名大写，如 `PT_COOKIE_HDTIME`）

### Step B：平台识别 — 判断站点框架

用 curl 抓取搜索页 HTML，对照下表识别平台类型：

| 特征 | 平台 | 搜索端点 | 解析模式 |
|------|------|---------|---------|
| `<table class="torrents">` 内嵌 `<table class="torrentname">`，含 `details.php?id=` | **NexusPHP** | `torrents.php?search=<kw>` | 复用经典解析器 |
| `<tr data="..."` 属性，种子行带 `data=` | **NexusPHP 变体** | `torrents.php?search=<kw>` | 复用 PTTime 解析器 |
| `/torrents.php` 返回 JSON | **NexusPHP（新版）** | `torrents.php?search=<kw>` | 直接 `json.loads()` |
| API 端点 `/api/torrents` 或 `/api/v1` | **UNIT3D** | API POST | 比照 M-Team API 模式 |
| 页面含 `torrent-search` class，卡片式布局 | **Gazelle / Luminance** | `torrents.php?searchstr=<kw>` | 需手写解析器 |
| 完全陌生的 DOM 结构 | **自定义** | 逐个分析 | 手写解析器 |

**识别命令**：

```bash
# 抓搜索页并保存
curl -b "c_secure_uid=...; c_secure_pass=..." \
  -x $PT_PROXY \
  "https://<site>/torrents.php?search=test" -o /tmp/<site>_search.html

# 快速判断框架
grep -oP 'torrents|torrentname|data-row|torrent-search|api/v1' /tmp/<site>_search.html | sort -u
```

### Step C：解析器适配

#### Case 1：复用已有解析器（NexusPHP 系列）

如果 `grep` 命中了 `torrentname` 或 `torrents` class：

   1. **经典 NexusPHP** → 复用 BTSchool/CarPT 的解析逻辑（见下方「NexusPHP Parser Notes」的「模式 2: 经典表格」）
    - 检查点：`details.php?id=` 链接格式、`download.php?id=` 格式、搜索页搜索参数名（`search` / `searchstr`）

   2. **NexusPHP `data=` 变体** → 复用 PTTime 解析逻辑（见下方「NexusPHP Parser Notes」的「模式 1: rowfollow 分离式」）
   - 检查点：`<tr data=ID>` 是否存在、stats cells 是否在 `</tr>` 之后

**无需重写代码，只需在 `pt_search.py` 中注册新站点**：
```python
# 在 SITES 字典中添加（参照 pt_search.py SITES dict）
SITES["new_site"] = {
    "name": "新站名",
    "url": "https://<site>",
    "parser": "nexusphp",
    "search": "/torrents.php?search={query}&notnewword=1",
    "needs_proxy": True,
    "categories": [],
}
```

#### Case 2：UNIT3D API

如果站点提供 REST API（类似 M-Team）：
- 找 API 文档（通常 `https://<site>/api` 或 Swagger）
- 确认认证方式（Bearer token / `x-api-key`）
- 对照 `mteam-api.md` 的模式适配

#### Case 3：完全自定义解析

> ⚠️ **禁止 Agent 自己写解析器代码。** 先完成 Step A/B 收集 HTML 样本和字段定位，然后将解析规格委托给 Claude Code / OpenCode 等编程 agent 实现。

**Agent 需要准备的交付物**（交给编程 agent）：

1. **HTML 样本**：保存搜索页到 `/tmp/<site>_search.html`
2. **种子列表容器选择器**：包含所有种子行的最外层元素（标签 + class/id）
3. **字段映射表**：
   - 标题（`<a>` 标签内的文本）
   - 详情页链接（`details.php?id=xxx`）
   - 下载链接（`download.php?id=xxx` 或 `dl.php?id=xxx`）
   - 大小（含 `GB`/`MB` 的 `<td>`）
   - 做种数/下载数/完成数
   - 免费/优惠标签（Freeleech / 50% / 2x 等）
4. **参考文件**：告诉编程 agent 参照 `scripts/pt_search.py` 中已有的 `_parse_nexusphp()` 或 `_parse_nexusphp_classic()` 的返回格式

**编程 agent 的任务**：
1. 写解析函数 `parse_<site>(html)` → 返回与已有解析器相同格式的 dict 列表
2. 在 `pt_search.py` 的 SITES 字典注册新站点 + 路由逻辑
3. 用 `python3 scripts/pt_search.py "test" --site <new> --limit 3` 自测验证

### Step D：验证

每步适配完成后立即验证：

```bash
# 1. 验证搜索返回结果
python3 scripts/pt_search.py "test" --site <new_site> --limit 3

# 2. 验证下载链接可访问
curl -I -b "<cookie>" -x $PT_PROXY "<download_url>" | head -3
# 应返回 Content-Type: application/x-bittorrent 或 Content-Disposition: attachment

# 3. 验证推送到 qBittorrent
curl -b <qb_cookie> -X POST '<qb_url>/api/v2/torrents/add' \
  --data-urlencode 'urls=<download_url>'
# 检查 qB 是否成功添加
```

### Step E：补充适配记录

适配完成后：

   1. **更新 NexusPHP Parser Notes（下方）** — 如果是新解析模式的变体，记录关键差异
2. **更新 skill 的 Supported PT Sites 表格** — 添加新站点行
3. **更新 `user-preferences.md`** — 补充新站点的代理需求配置
4. **更新 `templates/secrets.env.example`** — 添加新站点的 Cookie/API key 环境变量
5. **告知用户**：适配完成，附验证结果

### 适配检查清单

| # | 检查项 | 状态 |
|---|--------|------|
| 1 | Cookie / API Key 已写入 `secrets.env` | ☐ |
| 2 | 平台类型已识别 | ☐ |
| 3 | 搜索返回结果非空 | ☐ |
| 4 | 标题/大小/做种数/下载链接解析正确 | ☐ |
| 5 | 免费标签识别正确（如有） | ☐ |
| 6 | 脱敏/SSH 内容过滤（如有） | ☐ |
| 7 | 成人区搜索（如有） | ☐ |
| 8 | 代理配置正确 | ☐ |
| 9 | 下载链接可用（`application/x-bittorrent`） | ☐ |
| 10 | qBittorrent 推送成功 | ☐ |
| 11 | `pt_search.py` SITES 字典已注册 | ☐ |
| 12 | Skill 文档站点表格已更新 | ☐ |
| 13 | 模板文件已更新（secrets.env.example + user-preferences.md） | ☐ |

## NexusPHP Parser Notes

### 两种页面模式

#### 模式 1: rowfollow 分离式（PTTime）

```html
<tr data=47540>                              ← 标题行（含 data 属性）
  <td>category icon</td>
  <td class="embedded">                      ← 嵌套 table
    <a title="Title">Title</a>
    50%免费
  </td>
</tr>
<td class="rowfollow dn">0</td>              ← 统计单元格（在标题 </tr> 之后）
<td class="rowfollow">41.57<br>GB</td>       ← 大小
<td class="rowfollow"><b><a>7</a></b></td>   ← 做种数
<td class="rowfollow">0</td>                 ← 下载数
<tr data=59817>                              ← 下一个种子的标题行
```

**解析策略**: `_parse_nexusphp()`
- 找 `<tr data=ID>` 匹配标题和 promo
- 标题行 `</tr>` 到下一个 `<tr data=` 之间是统计区
- 大小: `<td>N.NN<br>GB</td>` 
- 种子: `<b>N</b>`（第一个 = seeders，第二个 = leechers）

#### 模式 2: 经典表格（BTSchool/CarPT/HDFans/1PTBar/SoulVoice/织梦）

```html
<table class="torrents">
  <tr><th>...</th></tr>                      ← 表头
  <tr>                                        ← 标题行（嵌套 table）
    <td class="embedded">
      <table class="torrentname">
        <tr>
          <td>
            <a title="Title">Title</a>
            50%免费
          </td>
        </tr>
      </table>
    </td>
    <td class="embedded">📥</td>              ← 下载图标
  </tr>
  ...stats cells between rows...              ← 同模式 1 的 stats 结构
  <tr>                                        ← 下一个标题行
```

**解析策略**: `_parse_nexusphp_classic()`
- ⚠️ 关键坑: `class="torrents"` 表内嵌套了内层 `<table>`，`</table>` 正则匹配会提前截断
- 解决方案: 不解析表格边界，直接用 download.php 链接定位
- 找每个 download.php 链接 → 向前找 `<tr` 开始 → 用深度计数找匹配 `</tr>`
- 标题在 `<a title="...">` 或 `details.php` 链接文本中
- Stats 在标题行 `</tr>` 和下一个 `<tr>` 之间（同模式 1）

### 通用规则

- 大小正则: `r'>\s*([\d.,]+)\s*(?:<br\s*/?>\s*)?(GB|MB|TB|KB)\s*<'`（处理 `<br>` 分隔）
- 种子数: stats 区第一个 `<b>N</b>` 通常是 seeders，第二个是 leechers
- Promo 检测: `halfdown`/`50%`/`pro_free` 在标题行 HTML 中
- 下载链接: 经典站无 passkey (`download.php?id=X`)，PTTime 有 passkey (`download.php?id=X&passkey=XX&uid=XX`)
