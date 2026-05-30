# M-Team (馒头) API 对接记录

## 基本信息

- **主站**: https://kp.m-team.cc/
- **API 主机**: https://api.m-team.cc/api（从主站 HTML 中的 `_APIHOSTS` JS 变量提取）
- **API 文档**: https://test2.m-team.cc/api/swagger-ui.html（需登录 test2 才能查看）
- **认证方式**: HTTP 请求头 `x-api-key: <token>`
- **Token 获取**: 控制台 → 实验室 → 存取令牌（自助获取）
- **代理**: API 从国内直连 403，需走 `PT_PROXY`。`mteam_api.py` 自动读取 `PT_PROXY`

## 官方规则

### 禁止 Cookie 访问

自开放 API KEY 后，如发现第三方工具仍通过 cookie 访问接口，**不排除禁用账户的可能**。

### 不允许第三方调用的端点

- `/admin/**`
- `/login`
- `/apikey/**`

### 允许第三方调用的端点

**`/member/` 前缀**:
- `/member/profile`
- `/member/base`
- `/member/bases`
- `/member/sysRoleList`
- `/member/getUserTorrentList`
- `/member/getCrimeRecords`
- `/member/queryUserLoginHistory`

**`/msg/` 前缀**:
- `/msg/statistic`
- `/msg/notify/statistic`

### API 速率限制

| 行为 | 限制 | 备注 |
|------|------|------|
| 下载种子配额 | 1000 个/每天 | 建议值 |
| 下载种子行为 | 100 个/每小时 | 建议值 |
| `/torrent/detail` | 100 次/每小时 | 建议值 |
| `/torrent/search` | 1000 次/近 24 小时 | 建议值 |

### 文档注意事项

官方文档（Swagger）存在 bug：请求数据格式 json/form 与实际可能不一致；必传参数可能不准确。建议辅以 web 调用情况使用。

## 请求规范

1. **只能 POST**，GET 返回 "Request method 'GET' is not supported"
2. **`code` 是字符串** `"0"`，不是整数 `0`，判断时用 `str(code) != "0"`
3. **HTTP Header**: `x-api-key: <token>`

## 已验证的 API 端点

### ✅ POST /api/torrent/search — 搜索种子

```python
POST https://api.m-team.cc/api/torrent/search
Headers: x-api-key, Content-Type: application/json
Body: {"keyword": "Wandering", "page": 1, "size": 25}
```

响应结构:
```json
{
  "code": "0",
  "message": "SUCCESS",
  "data": {
    "total": 226,
    "pageNumber": 1,
    "pageSize": 25,
    "data": [
      {
        "id": "1186409",
        "name": "标题",
        "size": 46296392211,
        "category": "419",
        "status": {
          "seeders": "10",
          "leechers": "0",
          "discount": "PERCENT_50"
        }
      }
    ]
  }
}
```

关键字段映射:
- `name` → 标题
- `size` → 大小（bytes）
- `status.seeders` → 做种数（字符串）
- `status.leechers` → 下载数（字符串）
- `status.discount` → 促销: PERCENT_50 / FREE / TWOUP / PERCENT_30

### ✅ POST /api/member/profile — 获取用户信息

需要参数 `{"userId": <USER_ID>}`。

### ✅ POST /torrent/genDlToken — 生成种子下载链接

**⚠️ Content-Type 陷阱（已验证）**:

genDlToken 对 `Content-Type` 头敏感。**不要**发 `Content-Type: application/json` + 空 body，会返回 `code: 1 請求參數錯誤`。

三种已验证可行的调用方式：

| 方式 | Content-Type | Body | 来源 |
|------|-------------|------|------|
| 空 body，不设 Content-Type | 不设置 | `b""` | **MoviePilot**（推荐，最简单） |
| 空 body + query string id | 不设置 | `b""` | **MoviePilot** 实际行为 |
| JSON body `{"visible": 1}` | `application/json` | `{"visible": 1}` | 实测可行 |
| multipart/form-data | `multipart/form-data` | `{id: torrent_id}` | **PT-depiler** |

**推荐方式**（与 MoviePilot 一致）：
```python
POST https://api.m-team.cc/api/torrent/genDlToken?id=<torrent_id>
Headers: x-api-key, Accept: application/json
Body: 空（不设 Content-Type）
# id 是 query 参数
```

**当前 pt-claw 代码问题**：
`mteam_api.py` 的 `_api_post()` 统一加了 `Content-Type: application/json` 头。
当 `body=None` 时实际发送 `Content-Type: application/json` + 空 body → M-Team 返回 `code: 1`。
**所有种子的下载链接生成已损坏**，不只是成人区。

响应:
```json
{
  "code": "0",
  "message": "SUCCESS",
  "data": "https://api.m-team.cc/api/rss/dlv2?sign=d6793499e...&t=1779942629&tid=1186409&uid=<USER_ID>"
}
```

返回的 URL 可直接用于 qBittorrent 添加下载。qBittorrent 发送 HTTP 请求时会自动带 `Accept: application/x-bittorrent`，服务器返回 `.torrent` 文件。

**注意**: genDlToken 返回的 URL 有时效性（sign 与 t 时间戳绑定），生成后尽快使用。

### 三方项目 genDlToken 对比

| 项目 | HTTP 方式 | Body | Content-Type | Cookie |
|------|----------|------|-------------|--------|
| **pt-claw** | POST, id 在 query string | 空 `b""` | `application/json` ❌ | 无 |
| **MoviePilot** | POST, id 在 query string | 空 | 不设置 ✅ | 显式禁用（"否则MT会出错"）|
| **PT-depiler** | POST | `{id: torrent_id}` | `multipart/form-data` | 无 |

MoviePilot 的 genDlToken 调用是延迟的：搜索时把请求参数 base64 编码存入 `enclosure` 字段，下载时才解码执行。

## 成人内容 / 9kg 区搜索

馒头成人内容位于独立的「9kg」区。普通搜索（不加 mode 参数）**仅返回非成人分类**（401-451 排除成人）。

### ✅ 已验证：`mode: "adult"` 参数

```python
POST https://api.m-team.cc/api/torrent/search
Headers: x-api-key, Content-Type: application/json
Body: {"keyword": "", "page": 1, "size": 25, "mode": "adult"}
```

**实测结果**：

| 方案 | 搜索结果 | 结论 |
|------|---------|------|
| `mode: "adult"` | ✅ 返回全部成人分类 (410/429/440 等) | **正确参数** |
| `visible: 1` | ❌ 返回普通分类 | 仅用于 genDlToken，不影响搜索 |
| `categories: [410]` | ❌ 独立使用返回 0 条 | 需配合 mode 使用 |
| `mode: "adult"` + `categories: [410]` | ✅ 精确过滤到 cat=410 | 按分类过滤可用 |

### 成人分类 ID（来自 PT-depiler mteam.ts）

| Category ID | 名称 |
|-------------|------|
| 410 | AV(有码)/HD Censored |
| 424 | AV(有码)/SD Censored |
| 437 | AV(有码)/DVDiSo Censored |
| 431 | AV(有码)/Blu-Ray Censored |
| 429 | AV(无码)/HD Uncensored |
| 430 | AV(无码)/SD Uncensored |
| 426 | AV(无码)/DVDiSo Uncensored |
| 432 | AV(无码)/Blu-Ray Uncensored |
| 436 | AV(网站)/0Day |
| 440 | AV(Gay)/HD |
| 425 | IV(写真影集) |
| 433 | IV(写真图集) |
| 411 | H-遊戲 |
| 412 | H-動畫 |
| 413 | H-漫畫 |

### 三方项目成人搜索对比

| 项目 | 成人搜索方式 | 参数位置 |
|------|------------|---------|
| **pt-claw** | 未实现 | — |
| **PT-depiler** | `mode: "adult"` in body，`searchEntry.area_adult` 预设（默认禁用） | `requestConfig.data.mode` |
| **MoviePilot** | `visible: 1` in search body（但这仅过滤活种，非成人区切换） | search params |

PT-depiler 的方案最完整：通过 `searchEntry` 机制区分综合/成人，`mode` 参数在 JSON body 中传递。douban/imdb 搜索强制 `mode: "normal"`。

### genDlToken 对成人种子

成人种子的 genDlToken **与普通种子完全一致**——使用同样的调用方式即可，无需额外参数。已实测验证成人种子 (cat=410, 429) 的 genDlToken 返回有效下载链接。

## API 故障模式（四类，渐进式降级）

| 模式 | HTTP 响应 | 表现 | 原因 | 处理 |
|------|----------|------|------|------|
| ① 限速 | `403 Forbidden` | JSON `code != "0"` | 搜索 1000次/24h 超限 | 等冷却或换 PTTime |
| ② 下线 | `405 Method Not Allowed` | Google 风格 HTML 错误页，POST 被拒 | API 服务端维护/关闭 | **跳过馒头**，走 PTTime → Sukebei |
| ③ DNS 失效 | `302 Found` → Google 搜索页 | `api.m-team.cc` 解析到 Google | DNS/托管配置问题 | **跳过馒头**，走 PTTime → Sukebei |
| ④ 国内 IP | `403 Forbidden` | 直连 403 | API 不允许国内 IP 直连 | **走 PT_PROXY** |

**模式②③时不要重试**：curl `-L` 跟随重定向只会得到 Google 错误页，不是临时故障。立即回退到其他源。

**排查命令**：
```bash
# 快速判断当前模式
curl -s -o /dev/null -w "%{http_code}" -X POST "https://api.m-team.cc/api/torrent/search" \
  -H "x-api-key: $MTEAM_API_KEY" -H "Content-Type: application/json" \
  -d '{"keyword":"test","page":1,"size":1}'

# 检查 DNS（模式③的根因）
dig api.m-team.cc +short
```
