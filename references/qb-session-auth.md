# qBittorrent Session Authentication

**qBittorrent Web API v5+ enforces CSRF protection.** Direct Basic Auth (`curl -u user:pass`) returns **403 Forbidden**.

## Working Pattern (Two-Step)

```python
import urllib.request, urllib.parse, json

# Step 1: Login to get SID cookie
login_data = f"username={urllib.parse.quote(user)}&password={urllib.parse.quote(passwd)}".encode()
login_req = urllib.request.Request(f"{url}/api/v2/auth/login", data=login_data)
resp = urllib.request.urlopen(login_req, timeout=10)
sid_cookie = resp.headers.get('Set-Cookie', '')

# Step 2: Use SID cookie for all subsequent requests
req = urllib.request.Request(f"{url}/api/v2/torrents/info")
req.add_header('Cookie', sid_cookie)
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read())
```

## Equivalent curl

```bash
# Login
curl -s -c /tmp/qb_cookie.txt -X POST \
  -d "username=USER&password=PASS" \
  "$QB_URL/api/v2/auth/login"

# Use cookie
curl -s -b /tmp/qb_cookie.txt "$QB_URL/api/v2/torrents/info"
```

## Affected Scripts

All pt-claw scripts that talk to qBittorrent (`qb_monitor.py`, `qb_add.py`, `qb_snapshot.py`, etc.) already handle this via `_qb_session.py`. The manual curl pattern above is for ad-hoc debugging.

## Pitfall

Using `source secrets.env && curl -u $QB_USER:$QB_PASS ...` will silently fail with 403. The `source` approach also breaks on cookie lines containing special characters (e.g., `sl-session=...==` triggers bash parse errors).
