# Cookie 过期 vs 代理被封 — 诊断流程

## 症状

PT 站搜索返回 HTTP 403 或空结果时，可能是：

- **Cookie 真正过期**（需要重新登录导出）
- **代理 IP 被 PT 站封禁**（Cookie 有效，但代理出口 IP 在黑名单）

## 诊断三步法

### Step 1: 去掉代理，直连测试

```python
# 走代理 → 403
req = urllib.request.Request(url, headers={"Cookie": cookie})
proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
opener = urllib.request.build_opener(proxy_handler)
# → HTTP 403

# 直连 → 200 OK  
req = urllib.request.Request(url, headers={"Cookie": cookie})
resp = urllib.request.urlopen(req)
# → 页面正常加载 → Cookie 有效，是代理被封！
```

### Step 2: 检查返回内容

```python
# 直连后检查页面内容
body = resp.read().decode()

if "控制面板" in body or "种子" in body or "bonus" in body:
    print("Cookie VALID")
elif "<form" in body and "password" in body:
    print("Cookie EXPIRED - redirected to login")
elif "cloudflare" in body.lower():
    print("Cloudflare JS challenge - need browser")
```

### Step 3: Cookie 长度检查

- 有效 Cookie 通常 150-200 字符（c_secure_uid + c_secure_pass + c_secure_ssl 等）
- 如果截断/丢失，长度会明显异常

## 已知站点的代理兼容性

| 站点 | 直连 | 代理 (<PROXY_HOST>) |
|------|------|----------------------|
| BTSchool | ✅ | ❌ 403 |
| CarPT | ✅ | ❌ 403 |
| HDFans | ✅ | ✅ |
| SoulVoice | ✅ | ✅ |
| 织梦 zmpt.cc | ✅ | ❌ 403 |
| PTTime | Cloudflare 盾 | 需浏览器 |

## 规则

**默认直连。只有直连超时/被墙/Cloudflare 盾的站才加代理。严禁无脑给所有请求加代理。**
