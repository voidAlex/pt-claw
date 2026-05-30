# 环境变量参考 — `secrets.env`

所有敏感配置存于 `secrets.env`（不入 Git）。模板见 `templates/secrets.env.example`。

脚本内部通过 `_load_env_file()` 安全读取（处理含 `=` 的 Cookie 值），**禁止 `source secrets.env`**。

## PT 站点

| 变量 | 说明 |
|------|------|
| `PT_COOKIE_PTTIME` | PTTime Cookie |
| `PT_COOKIE_BTSCHOOL` | BTSchool Cookie |
| `PT_COOKIE_CARPT` | CarPT Cookie |
| `PT_COOKIE_HDFANS` | HDFans Cookie |
| `PT_COOKIE_1PTBA` | 1PTBar Cookie |
| `PT_COOKIE_SOULVOICE` | SoulVoice Cookie |
| `PT_COOKIE_ZMPT` | 织梦 (zmpt.cc) Cookie |
| `PT_COOKIE_PTSKIT` | PTSkit (拾刻) Cookie |
| `PT_COOKIE_PTHOME` | PTHome (铂金家) Cookie |
| `PT_COOKIE_HDSKY` | HDSky (天雪) Cookie |
| `PT_COOKIE_HDHOME` | HDHome (家园) Cookie |
| `PT_COOKIE_AUDIENCES` | Audiences (观众) Cookie |
| `PT_COOKIE_KEEPFRDS` | KeepFriends (朋友) Cookie |
| `PT_COOKIE_TTG` | ToTheGlory (TTG) Cookie |
| `MTEAM_API_KEY` | M-Team API Key。**禁止 Cookie——会封号**。**必须同时配置 `PT_PROXY`** |

## 下载器

| 变量 | 说明 |
|------|------|
| `QBITTORRENT_URL` | qBittorrent 地址（含端口） |
| `QBITTORRENT_USER` | qBittorrent 用户名 |
| `QBITTORRENT_PASS` | qBittorrent 密码 |
| `QB_CLEANUP_DRY_RUN` | 设为 `1` 时公开种清理仅报告不删除（安全开关，可选） |

## Jellyfin（可选，未配置不影响下载）

| 变量 | 说明 |
|------|------|
| `JELLYFIN1_URL` | JF1 地址 |
| `JELLYFIN1_API_KEY` | JF1 API Key |
| `JELLYFIN2_URL` | JF2 地址 |
| `JELLYFIN2_API_KEY` | JF2 API Key |

## 网络

> ⚠️ **致命警告**：不要设 `HTTP_PROXY` / `HTTPS_PROXY`！用 `PT_PROXY` 代替。

| 变量 | 说明 |
|------|------|
| `PT_PROXY` | PT 搜索代理地址，脚本按站点 `needs_proxy` 标记自动应用 |

## javbus-api（可选）

| 变量 | 说明 |
|------|------|
| `JAVBUS_API_URL` | javbus-api 地址（如 `http://localhost:8922`） |

## CookieCloud（可选，未配置则手动管理 Cookie）

| 变量 | 说明 |
|------|------|
| `COOKIE_CLOUD_HOST` | CookieCloud 服务器地址 |
| `COOKIE_CLOUD_UUID` | 用户 UUID |
| `COOKIE_CLOUD_PASS` | 加密密码 |

## 用户偏好（存入 `user-preferences.md`）

- 清晰度偏好（4K/1080p/720p）
- 编码偏好（HEVC/AVC/AV1）
- 下载路径分类映射
- 成人内容 PT 做种阈值 & 版本优选顺序
- 关注列表 (`pt_wishlist.json`)
