# Jellyfin 演员片库统计

## 用途

回答「片库有哪些明星」「谁的最多」类问题。

## 技术要点

- 端点：`GET /Items?parentId=<library_id>&recursive=true&includeItemTypes=Movie&fields=People&startIndex=0&limit=200`
- `fields=People` 关键：不传此参数则 `People` 数组为空
- 分页：JF 每次最多返回约 200 条，需通过 `startIndex` + `TotalRecordCount` 翻页
- 700+ 部影片约需 4 次请求

## 示例代码

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

## 注意事项

- 同一演员可能出现多个名字（日文名 vs 中文译名），如「桃乃木香奈」和「桃乃木かな」是同一人
- JF1 `parentId` 需先通过 `/Library/VirtualFolders` 获取
- JF 响应不含演员的 `Id`，只能按 `Name` 字符串匹配
