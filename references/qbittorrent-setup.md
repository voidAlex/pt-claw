# qBittorrent Integration Reference

## Connection

qBittorrent 地址、用户名、密码从环境变量读取：

| 变量 | 说明 |
|------|------|
| `QBITTORRENT_URL` | Web UI 地址（含端口） |
| `QBITTORRENT_USER` | 登录用户名 |
| `QBITTORRENT_PASS` | 登录密码 |

所有脚本通过 `_env()` 读取，不从 skill 内部硬编码。

## 分类与路径 — 动态读取

**禁止在 skill 中硬编码分类名和路径。** 使用 API 动态读取：

```bash
# 读取用户实际分类
curl -b <cookie> '<QBITTORRENT_URL>/api/v2/torrents/categories'

# 示例返回：{"电影": {"savePath": "/path/to/movies"}, "电视剧": {...}}
```

Agent 在 Step 4 推送下载时，先调此 API 获取真实分类列表，再匹配或让用户选择。

## 关键 API

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/v2/auth/login` | POST | 登录 |
| `/api/v2/torrents/add` | POST | 添加种子 |
| `/api/v2/torrents/addTags` | POST | 打标签 |
| `/api/v2/torrents/categories` | GET | 读取分类 |
| `/api/v2/torrents/setCategory` | POST | 修改分类 |
| `/api/v2/torrents/setLocation` | POST | 修改路径 |
| `/api/v2/torrents/info` | GET | 查询种子状态 |
| `/api/v2/torrents/delete` | POST | 删除种子 |
