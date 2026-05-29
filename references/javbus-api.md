# javbus-api 参考

部署地址：`http://localhost:8922`，容器名 `javbus-api`，Docker 代理已配。

## 端点速查

### 搜索影片
```
GET /api/movies/search?keyword=<关键词>&magnet=exist&page=1
```
- `keyword`：必填，中文需 URL 编码（curl 用 `-G --data-urlencode`）
- `magnet`：`exist`（仅有磁链）| `all`（全部）
- 返回：`{movies: [{id, title, img, date, tags}], pagination: {...}, keyword}`

### 影片详情（含封面+预览图+gid）
```
GET /api/movies/<番号>
```
返回关键字段：
- `img`：封面大图 URL
- `samples[]`：内容预览截图，每项有 `src`(大图) + `thumbnail`(缩略图)，最多 20 张
- `stars[]`：演员 `{id, name}`
- `director`、`genres[]`、`series`
- `gid` + `uc`：获取磁链必需
- `date`、`videoLength`

### 磁链列表（结构化）
```
GET /api/magnets/<番号>?gid=<GID>&uc=<UC>&sortBy=size&sortOrder=desc
```
- `gid`、`uc`：从影片详情获取，必填
- `sortBy`：`size` | `date`
- `sortOrder`：`desc` | `asc`

返回数组，每条：
```json
{
  "id": "hash",
  "link": "magnet:?xt=urn:btih:...",
  "isHD": true,
  "hasSubtitle": true,
  "title": "SNOS-151-C",
  "size": "6.38GB",
  "numberSize": 6845104128,
  "shareDate": "2026-04-13"
}
```

### 演员详情
```
GET /api/stars/<starId>
```
返回演员信息 + 作品列表。starId 从影片详情的 `stars[].id` 获取。

### 最新影片
```
GET /api/movies?type=normal     # 有码
GET /api/movies?type=uncensored # 无码
```

## 部署记录

```bash
# Docker daemon 代理配置（/etc/systemd/system/docker.service.d/proxy.conf）
[Service]
Environment="HTTP_PROXY=<PROXY_HOST>"
Environment="HTTPS_PROXY=<PROXY_HOST>"
Environment="NO_PROXY=localhost,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

# 容器
docker run -d --name=javbus-api --restart=unless-stopped \
  -p 8922:3000 -e HTTP_PROXY=<PROXY_HOST> \
  ovnrain/javbus-api
```

## 与裸爬对比

| 能力 | 裸爬 | javbus-api |
|------|------|------------|
| 磁链 | HTML 正则提取，需去重 | 结构化 JSON，HD/字幕/大小标记 |
| 封面 | 需额外解析 | `img` 字段直接给 |
| 预览截图 | 需从 sample 区提取 | `samples[]` 直接给 |
| 排序 | 无 | `sortBy=size/date` |
| 演员作品 | 需开 star 独立页 | `/api/stars/{id}` |
| 搜索 | 不支持 | `/api/movies/search` |
