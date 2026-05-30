# 成人内容 — API、搜索区与追剧链路

> ⚠️ **必须先检查开关**：搜索前读 `user-preferences.md` 的 `## 成人内容 → 启用` 字段。`enabled: false` 或未配置 → 拒绝成人搜索请求。

## javbus-api — 影片元数据与磁链 API（可选）

不部署也能通过裸爬获取磁链。部署后数据更结构化，磁链可排序，封面预览一键获取。

### 部署

```bash
cp templates/docker-compose.javbus-api.yml ~/javbus-api/docker-compose.yml
# 编辑 docker-compose.yml，将 <PT_PROXY> 替换为实际代理地址
docker compose -f ~/javbus-api/docker-compose.yml up -d
```

部署后在 `secrets.env` 中设置 `JAVBUS_API_URL=http://localhost:8922`。

### API 端点

| 端点 | 功能 | 返回 |
|------|------|------|
| `GET /api/movies/{番号}` | 影片详情 | 封面、预览截图(≤20张)、演员、导演、标签、gid、uc |
| `GET /api/magnets/{番号}?gid=X&uc=Y` | 磁链列表 | hash、大小(bytes)、HD/字幕标记、日期 |
| `GET /api/movies/search?keyword=xxx` | 关键词搜索 | 番号+标题+封面+标签 |
| `GET /api/stars/{starId}` | 演员详情 | 演员名、作品列表、头像 |

磁链排序：`sortBy=size|date` + `sortOrder=desc|asc`

### 磁链获取是两步操作

`/api/movies/{番号}` 返回详情（含 gid/uc），`/api/magnets/{番号}?gid=X&uc=Y` 才返回磁链：

```bash
MOVIE=$(curl -s "http://localhost:8922/api/movies/$CODE")
gid=$(echo "$MOVIE" | python3 -c "import sys,json; print(json.load(sys.stdin)['gid'])")
uc=$(echo "$MOVIE" | python3 -c "import sys,json; print(json.load(sys.stdin)['uc'])")
curl -s "http://localhost:8922/api/magnets/$CODE?gid=$gid&uc=$uc"
```

磁链版本选择优先级：`-C`（字幕）> `-U`（去码）> `uncensored` > `-AI` > 标准版 > `4K`

### 裸爬模式（无 javbus-api 时）

```bash
# Step 1: 影片详情
curl -s "https://www.javbus.com/<CODE>" -x <proxy> | python3 -c "
import sys,re,json; t=sys.stdin.read()
info={'cover': (r:=re.search(r'class=\"bigImage\"[^>]*href=\"([^\"]+)\"', t)) and r.group(1),
      'gid': (r:=re.search(r'var gid = (\d+)', t)) and r.group(1),
      'uc': (r:=re.search(r'var uc = (\d+)', t)) and r.group(1)}
print(json.dumps(info, ensure_ascii=False))
"
# Step 2: Ajax 拿磁链
curl -s "https://www.javbus.com/ajax/uncledatoolsbyajax.php?gid=<GID>&lang=zh&img=...&uc=<UC>" \
  -x <proxy> -H "Referer: https://www.javbus.com/<CODE>"
```

## PT 站成人区搜索

### PTTime

- **页面**: `https://www.pttime.org/adults.php`
- **按番号**: `searchstr=SSIS-448`
- **按演员**: `actor=浅野心`（演员在 tag 里不在标题里，必须用 `actor=`）
- **HTML**: 与主页 `torrents.php` 相同（NexusPHP 双行结构）
- **pt-claw**: 已适配，`pt_search.py --site pttime --adult`

| Category ID | 名称 |
|-------------|------|
| 440 | 9kg-步兵(无码) |
| 441 | 9kg-骑兵(有码) |
| 442 | 9kg-III(三级) |
| 443-449 | H漫/H游/H书/H图/H音/H综/H同 |

### M-Team

- **API 搜索**: `POST /api/torrent/search` body `{"keyword": "", "mode": "adult", "page": 1, "size": 25}`
- **限速**: 1000 次/24h，超限 403
- **Web 页面**: `https://kp.m-team.cc/browse/adult`（仅浏览，禁止 Cookie 调 API）
- **pt-claw**: 已适配

### PTSkit（拾刻）

- **成人区**: `/special.php`（「十八禁」）
- **分类**: 410=国产, 411=日本, 412=欧美
- **pt-claw**: 已适配

## 公开磁链源（PT 做种不足时回退）

优先级：JavBus（javbus-api）→ Sukebei Nyaa（有种数）→ JavBus 裸爬

| 源 | 类型 | 做种数 | 封面 | 脚本 |
|----|------|--------|------|------|
| javbus-api | REST API | ❌ | ✅ | `javbus_magnet.py --api` |
| Sukebei Nyaa | RSS | ✅ | ❌ | `sukebei_search.py` |
| JavBus 裸爬 | HTML+Ajax | ❌ | ✅ | `javbus_magnet.py --scrape` |

### 公开磁链筛选规则

**🚫 排除**：广告词（加群/QQ/微信/tg）、合集/pack、预告/sample、纯 hash 标题、>5 个视频文件

**✅ 优先**：带 FHDC/HD/4K/中文字幕/HEVC 标签、清晰番号+标题、做种 ≥1

### 公开磁链管理

| 规则 | PT 私有种子 | 公开磁链 |
|------|-----------|---------|
| 做种 | 必须保种 | ❌ 下完删种保文件 |
| 上传 | 正常做种 | 🚫 禁止上传 |
| 完成处理 | 持续做种 | 自动停止+删除 |

`_cron_check.py`（每 15 分钟）自动清理已完成公开磁链，安全防线：占比 >20% 跳过，单次 ≤50。

## Cron 成人追剧优化链路

定时任务场景（无用户交互，需快速完成）的成人演员追剧链路。

### 背景

- PTTime/M-Team 成人区搜 SONE/SNOS/FNS 等新番号 **全部 0 结果**
- 逐部调 `pt_search.py --adult` 浪费多站 × 20 次 API 调用
- Sukebei Nyaa 对番号覆盖率高

### 推荐链路

```
javbus-api 获取片单
  → download_history filter（本地 JSON）
  → JF 成人实例去重
  → PT 搜索 ❌ 跳过
  → Sukebei Nyaa 批量搜索
  → 按做种数排序 → qb_add.py 批量推送
  → download_history 记录
```

| 步骤 | 交互模式 | Cron 模式 |
|------|---------|----------|
| 元数据 | JavBus 裸爬 | javbus-api |
| PT 搜索 | pt_search.py --adult | **跳过** |
| 公开源 | 按需回退 | 直接 Sukebei 批量 |
| Push | 逐部确认 | 批量 stdin JSON |

### 演员名歧义

「浅野心」可能指 浅野こころ 或 浅野心愛。策略：javbus-api 搜名获取所有匹配 → 按作品数判断主次 → 全部纳入候选 → JF + 下载历史去重。

### qB 批量推送注意

- `qb_add.py --stdin` 读取 JSON 行
- `"Fails."` = 种子已存在，补标签即可
- 所有公开磁链必须 `"video_only": true` + `"tags": ["sukebei"]`
- 推送后立即 `download_history.py add` 记录
