# qBittorrent 推送两步法（含标签）

## 问题

PT 站的 `download.php?id=X` 需要 PT 站的 Cookie 才能访问。如果用 `urls=<download_url>` 方式把链接直接传给 qBittorrent，qB 返回 `Ok.` 但实际不会添加任何任务——因为 qB 自己去拉 URL 时没有 PT Cookie，被拒了。

**这是静默失败**：API 返回成功，qB 列表里却看不到新种子。

## 正确流程（五步）

### Step 1: 用 PT Cookie 下载 .torrent 到本地

```python
import urllib.request

pt_cookie = "<从 .env 读取>"
dl_url = "https://pt.btschool.club/download.php?id=240323"

req = urllib.request.Request(
    dl_url,
    headers={"Cookie": pt_cookie, "User-Agent": "Mozilla/5.0"}
)
with urllib.request.urlopen(req, timeout=30) as resp:
    torrent_data = resp.read()

# 验证是 torrent 文件
assert torrent_data[:2] == b'd8', "Not a torrent file!"

with open('/tmp/torrent.torrent', 'wb') as f:
    f.write(torrent_data)
```

### Step 2: 登录 qB → multipart 上传本地文件

```python
import http.cookiejar, urllib.request, os, binascii

qb_url = "http://<QB_HOST>"
qb_user = "<user>"
qb_pass = "<pass>"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
login_data = f"username={urllib.parse.quote(qb_user)}&password={urllib.parse.quote(qb_pass)}".encode()
opener.open(f"{qb_url}/api/v2/auth/login", data=login_data)

boundary = '----QB' + binascii.hexlify(os.urandom(8)).decode()
with open('/tmp/torrent.torrent', 'rb') as f:
    file_bytes = f.read()

body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="torrents"; filename="download.torrent"\r\n'
    f'Content-Type: application/x-bittorrent\r\n\r\n'
).encode() + file_bytes + f'\r\n--{boundary}--\r\n'.encode()

add_req = urllib.request.Request(
    f"{qb_url}/api/v2/torrents/add",
    data=body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)
opener.open(add_req)
```

### Step 3: 验证（必做！）

```python
with opener.open(f"{qb_url}/api/v2/torrents/info?sort=added_on&reverse=true&limit=5") as resp:
    recent = json.loads(resp.read())
    print(f"Latest: {[t['name'][:40] for t in recent]}")
```

### Step 4: 设置分类和路径

```python
with opener.open(f"{qb_url}/api/v2/torrents/categories") as resp:
    cats = json.loads(resp.read())

cat_data = f"hashes={hash}&category={urllib.parse.quote('<分类名>')}".encode()
opener.open(f"{qb_url}/api/v2/torrents/setCategory", data=cat_data)

path_data = f"hashes={hash}&location={urllib.parse.quote('<目标路径>')}".encode()
opener.open(f"{qb_url}/api/v2/torrents/setLocation", data=path_data)
```

### Step 5: 打站点标签（必须！）

```python
# 标签 = source/site_id: mteam/pttime/btschool/carpt/hdfans/1ptba/soulvoice/zmpt/sukebei/javbus
tag_data = f"hashes={hash}&tags={urllib.parse.quote('pttime')}".encode()
opener.open(f"{qb_url}/api/v2/torrents/addTags", data=tag_data)
```

或用 `qb_add.py` 一步完成：`python3 scripts/qb_add.py "magnet:..." --tags sukebei`

**手动 curl 补标签**：
```bash
HASH=$(curl -s -b /tmp/qb_cookies.txt \
  "http://<QB_HOST>/api/v2/torrents/info?sort=added_on&reverse=true&limit=5" \
  | python3 -c "import sys,json;[print(t['hash']) for t in json.load(sys.stdin) if '<关键词>' in t['name']]")
curl -s -b /tmp/qb_cookies.txt -X POST \
  "http://<QB_HOST>/api/v2/torrents/addTags" \
  --data-urlencode "hashes=$HASH" --data-urlencode "tags=sukebei"
```

## 常见翻车场景

1. **分类名不匹配**：qB 里叫"电视剧"，却传了 `category=tv` → 分类为空
2. **multipart upload 不认 query param**：`/torrents/add?category=电视剧` 的 `?category=` 在 multipart 上传时可能不生效 → 事后 `setCategory` + `setLocation` 修正
3. **Cookie 过期**：.torrent 下载返回登录页 HTML 而不是 bencode → Cookie 过期
4. **代理干扰**：下载 .torrent 走代理可能被 PT 站拒绝（403）→ 先试直连
5. **忘记打标签**：没打站点标签 → 后续无法按来源筛选，比率管理困难
