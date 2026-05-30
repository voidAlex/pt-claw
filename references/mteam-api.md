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
3. **HTTP Header**: `x-api-key: <token>`，`Content-Type: application/json`

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

```python
POST https://api.m-team.cc/api/torrent/genDlToken?id=<torrent_id>
Headers: x-api-key, Accept: application/json
# id 是 query 参数，不是 body 参数
```

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

## 成人内容 / 9kg 区搜索

馒头成人内容位于独立的「9kg」区（页面标题 "Adult"）。当前搜索脚本 `pt_search.py` 的 API 调用**不包含成人区**，仅搜索通用影视区。

**API 方案**（推荐，待验证）:
- `mode: "adult"` 参数
- `categories: [9]` 参数（9kg 分类 ID）

**Web 方案**（备选）:
- 成人区地址: `https://kp.m-team.cc/browse/adult`
- ⚠️ 需要有效的 web cookie，但 M-Team **禁止 Cookie 访问 API**
