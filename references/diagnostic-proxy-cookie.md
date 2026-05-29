# Cookie 过期 vs 代理被封 vs IP 绑定 — 诊断流程

## 症状

PT 站搜索返回 HTTP 403 或空结果时，可能是：

- **Cookie 真正过期**（需要重新登录导出）
- **代理 IP 被 PT 站封禁**（Cookie 有效，但代理出口 IP 在黑名单）
- **NexusPHP IP 绑定**（Cookie 有效但绑定了登录时的 IP，换 IP 后失效）

## 诊断流程

### Step 1: 检查是否为 needs_proxy 站点

NexusPHP 站点的 `c_secure_*` cookie 绑定登录时的 IP。如果浏览器通过代理登录，服务器也必须走相同出口 IP 的代理才能用。

| 站点 | 直连 | 代理 | 说明 |
|------|------|------|------|
| PTTime | ✅ | ❌ | 直连 OK |
| HDFans | ✅ | — | 直连 OK |
| 1PTBar | ✅ | — | 直连 OK |
| BTSchool | ❌ 403 | ✅ | 需代理（cookie IP 绑定） |
| CarPT | ❌ 403 | ✅ | 需代理（cookie IP 绑定） |
| SoulVoice | ❌ 403 | ✅ | 需代理（cookie IP 绑定） |
| 织梦 zmpt.cc | ❌ 403 | ✅ | Cloudflare + 需代理 |

对于 `needs_proxy=True` 的站点：**必须走代理**，代理出口 IP 需与浏览器登录时一致。直连 403 是正常行为，不是 cookie 过期。

### Step 2: 代理也 403 → 检查 cookie 过期

```python
# 代理 + cookie → 仍然 403
# 检查 CookieCloud 的 update_time 和 cookie 过期时间
# cookie_sync.py 解密后可见 update_time 和各 cookie 的 expirationDate
```

CookieCloud `update_time` 可判断最近同步时间。`c_secure_*` 的 `expirationDate` 可判断过期日期（Unix 时间戳）。

### Step 3: 检查返回内容

```python
body = resp.read().decode()

if "控制面板" in body or "种子" in body or "bonus" in body:
    print("Cookie VALID")
elif "<form" in body and "password" in body:
    print("Cookie EXPIRED - redirected to login")
elif "cloudflare" in body.lower():
    print("Cloudflare JS challenge - need browser")
```

### Step 4: Cookie 长度检查

- 有效 Cookie 通常 150-200 字符（c_secure_uid + c_secure_pass + c_secure_ssl 等）
- 如果截断/丢失，长度会明显异常

## 规则

**直连优先。`needs_proxy=True` 的站走代理。直连失败时自动代理重试。代理出口 IP 必须与浏览器 CookieCloud 同步时的出口一致。**
