# M-Team (馒头) API 对接记录

## 基本信息

- **主站**: https://kp.m-team.cc/
- **API 主机**: https://api.m-team.cc/api（从主站 HTML 中的 `_APIHOSTS` JS 变量提取）
- **API 文档**: https://test2.m-team.cc/api/swagger-ui.html（需登录 test2 才能查看，主站 Cloudflare 拦截）
- **认证方式**: HTTP 请求头 `x-api-key: <token>`
- **Token**: 从 `MTEAM_API_KEY` 环境变量读取（控制台→實驗室→存取令牌 获取）

## 重要规则

1. **只能 POST**，GET 返回 "Request method 'GET' is not supported"
2. **`code` 是字符串** `"0"`，不是整数 `0`，判断时用 `str(code) != "0"`
3. **禁止用 cookie 访问 API**，否则可能被封号
4. 搜索限速: 1000次/24小时
5. 下载限速: 100个/小时

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

## ✅ 下载端点（已解决）

### POST /torrent/genDlToken — 生成种子下载链接

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

## API 故障模式（三类，渐进式降级）

| 模式 | HTTP 响应 | 表现 | 原因 | 处理 |
|------|----------|------|------|------|
| ① 限速 | `403 Forbidden` | JSON `code != "0"` | 搜索 1000次/24h 超限 | 等冷却或换 PTTime |
| ② 下线 | `405 Method Not Allowed` | Google 风格 HTML 错误页，POST 被拒 | API 服务端维护/关闭 | **跳过馒头**，走 PTTime → Sukebei |
| ③ DNS 失效 | `302 Found` → Google 搜索页 (`<title>Google</title>`) | `api.m-team.cc` 和 `api.m-team.io` 都解析到 Google | DNS/托管配置问题 | **跳过馒头**，走 PTTime → Sukebei |

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

## 已知限制

### 成人内容 / 9kg 区搜索

馒头成人内容位于独立的「9kg」区（页面标题 "Adult"）。当前搜索脚本 `pt_search.py` 的 API 调用**不包含成人区**，仅搜索通用影视区。搜索 SSIS/番号类内容需要：

**API 方案**（推荐，待验证）:
- `mode: "adult"` 参数
- `categories: [9]` 参数（9kg 分类 ID）
- 具体参数尚未验证（API 返回 403 时未能测试）

**Web 方案**（备选）:
- 成人区地址: `https://kp.m-team.cc/browse/adult`
- 搜索 URL: `https://kp.m-team.cc/browse/adult?search={query}`（待验证）
- ⚠️ 需要有效的 web cookie（当前 `pt_cookies.json` 中 mteam 无有效 cookie）

### 搜索频率限制

API 搜索限制 **1000 次/24 小时**。超限后返回 `403 Forbidden`，需等待冷却。开发调试时注意控制频率，不要短时间内大量请求。
