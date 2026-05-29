# Cron 成人追剧高效执行模式

Cron 自动追剧处理成人演员关注时的优化链路。适用于定时任务场景（无用户交互，需快速完成）。

## 背景

实测发现：
- PTTime/M-Team 成人区搜索 SONE/SNOS/FNS 等新番号系列 **全部返回 0 结果**
- 每部单独调 `pt_search.py --adult` 浪费 8 站 × 20 次 API 调用，耗时且无产出
- Sukebei Nyaa 对番号覆盖率高，做种数可直接判断活性

## 推荐链路（Cron 模式）

```
JavBus/javbus-api 获取片单
  → download_history filter（本地 JSON，毫秒级）
  → JF1 API 去重（按番号逐条查）
  → PT 搜索 ❌ 跳过（成人番号几乎无结果）
  → Sukebei Nyaa 批量搜索（Python 脚本，代理直连）
  → 按做种数排序 → qb_add.py 批量推送
  → download_history 记录
```

## 对比

| 步骤 | 原流程（交互模式） | Cron 优化模式 |
|------|-----------------|-------------|
| 元数据 | JavBus 裸爬或 star 页 | **javbus-api** `/api/movies/search?keyword=` |
| PT 搜索 | pt_search.py --adult（每部） | **跳过** |
| 公开源 | 按需回退 | **直接 Sukebei**，一次性批量 |
| Push | 逐部确认路径 | 批量 stdin JSON，统一 category/tags |

## javbus-api 关键端点

部署后（`docker run -d -p 8922:3000 ovnrain/javbus-api`）：

```
GET /api/movies/search?keyword=<演员名>&page=1&magnets=filter
```

- 支持中文名搜索（如 `浅野`、`浅野こころ`）
- 返回分页，每页 30 条
- 自动过滤无关结果（同名不同人会被聚合）
- 比裸爬快 10x，无需处理 Cloudflare

## Sukebei 批量搜索 Python 模板

```python
import urllib.request, urllib.parse
from xml.etree import ElementTree as ET

PROXY = "<PROXY_HOST>"
SUKEBEI_RSS = "https://sukebei.nyaa.si/?page=rss"
NYAA_NS = "https://sukebei.nyaa.si/xmlns/nyaa"

proxy_handler = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
opener = urllib.request.build_opener(proxy_handler)
opener.addheaders = [("User-Agent", "Mozilla/5.0")]

def search_sukebei(code):
    url = f"{SUKEBEI_RSS}&q={urllib.parse.quote(code)}"
    req = urllib.request.Request(url)
    with opener.open(req, timeout=20) as resp:
        root = ET.fromstring(resp.read().decode())
    results = []
    for item in root.findall(".//item"):
        title = item.find("title").text
        seeders = int(item.find(f"{{{NYAA_NS}}}seeders").text or 0)
        ih = item.find(f"{{{NYAA_NS}}}infoHash").text
        results.append({"title": title, "seeders": seeders, "hash": ih})
    results.sort(key=lambda x: x["seeders"], reverse=True)
    return results
```

## qB 批量推送注意事项

- `qb_add.py --stdin` 读取 JSON 行
- `"Fails."` 响应 = 种子已存在，不是错误 → 补打标签即可
- 所有公开磁链必须 `"video_only": true` + `"tags": ["sukebei"]`
- 推送后立即调用 `download_history.py add` 记录

## 演员名歧义处理

用户关注名可能不精确（如「浅野心」可能指 浅野こころ 或 浅野心愛）。策略：
1. 用 javbus-api 搜演员名，获取所有匹配结果
2. 按作品数量和知名度判断主次（S1 专属 > FALENO 新人）
3. 在报告中标注两位演员的来源（如「浅野こころ 46部 + 浅野心愛 10部」）
4. Cron 无用户交互 → 全部纳入下载候选，由 JF1 和下载历史去重
