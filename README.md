# pt-claw.skill

> v3.3.0 — 多站 PT 种子搜索与下载技能，兼容任意 AI Agent。

对话式搜索 115 个 PT 站资源、推送到 qBittorrent、监控下载进度——全程纯脚本，无 Prowlarr/Jackett 依赖。

## 功能

- **115 站支持（15 核心 + 100 扩展）**：核心 → M-Team (API)、PTTime、BTSchool、CarPT、HDFans、1PTBar、SoulVoice、织梦、PTSkit、PTHome、HDSky、HDHome、Audiences、KeepFriends、ToTheGlory；扩展 → PTer(猫站)、HDArea、CHDBits、OurBits、HDDolby、HDKylin、HDTime、HDU、HhanClub(憨憨)、海胆、天使、春天(CMCT)、TCCF(ET8)、TLF(吐鲁番)、JoyHD、北洋、葡萄(SJTU)、北邮人(BYRBT)、蝴蝶(HUDBT)、南洋PT、龟站(KamePT) 等 100 站
- **双引擎搜索**：Cookie 直连站点 + M-Team REST API
- **智能去重**：下载历史记录 + Jellyfin 片库感知，删了的内容不会重复下载
- **自动回退**：PT 做种不足时自动回退到公开磁链
- **站点标签**：每次下载自动打上来源标签（mteam/pttime/sukebei 等）
- **定时任务**：进度监控+公开种清理(15m)、每日追剧(10:00)、Cookie同步/保活(视配置)、刷流保号(每日)
- **辅种**：多站 cross-seed 三阶匹配（infoHash→名称+体积→文件列表）
- **刷流保号**：可选 Freeleech/2x上传 促销种子自动下载做种，到期自动清理
- **详情页直推**：给个 PT 站详情页链接，自动下载 .torrent 推送 qB（通用所有 115+ 站）

## 使用方式

这是给 AI Agent 用的技能，加载后通过对话操作，不需要手动跑脚本。

**推荐使用 DeepSeek V4 Pro 模型**，该模型在工具调用和多步骤任务编排方面表现最佳。

```
你：搜一下流浪地球2
     → Agent 自动调 pt_search.py 搜所有站，展示结果让你挑

你：下载第一个
     → Agent 推 qBittorrent，打站点标签，记下载历史

你：关注诺兰的电影
     → Agent 写关注列表，每天 10 点自动检查新资源

你：这个链接下载 https://pt.btschool.club/details.php?id=172580
     → Agent 自动识别站点、下载种子、推送到 qBittorrent
```

脚本是 Agent 内部调用的，使用者无需关心命令行参数。

## 环境要求

- Python 3.10+
- `cryptography`（CookieCloud 同步需要：`pip install cryptography`）
- qBittorrent Web UI 已开启
- PT 站 Cookie（存于 `secrets.env`）
- M-Team API Key（可选，API 搜索需要）

## 配置

首次使用时，Agent 会交互式引导配置。参考 `templates/secrets.example.env` 了解所需环境变量。

## 脚本清单

| 脚本 | 用途 |
|------|------|
| `pt_search.py` | 多站搜索（NexusPHP + M-Team API） |
| `pt_download.py` | 详情页 URL 直接下载推送 qB（通用所有站） |
| `qb_add.py` | 添加种子到 qBittorrent（含文件选择 + 本地文件上传 + 补分类） |
| `qb_monitor.py` | qB 全功能查询（状态/过滤/删除/死种诊断） |
| `qb_public_cleanup.py` | 公开磁链清理（手动使用，cron 已合并到 `_cron_check.py`） |
| `qb_snapshot.py` | 删种备份与恢复（backup/restore/list 合一） |
| `sukebei_search.py` | Sukebei 公开磁链搜索 |
| `javbus_magnet.py` | JavBus 磁链爬取 |
| `javbus_star.py` | 演员片单交叉对比（javbus-api → JF + 历史） |
| `jf_query.py` | Jellyfin 查询（演员排名/搜索/去重） |
| `download_history.py` | 下载历史追踪（防重复 + ignore/unignore 忽略名单） |
| `wishlist_manager.py` | 愿望单管理（add/remove/list 演员/影片/番号） |
| `pt_ratio_boost.py` | Freeleech 刷流保号 |
| `site_profile.py` | 多站用户信息查询（默认只查已配置站） |
| `cross_seed.py` | 多站辅种验证与推送（下载.torrent→SHA1比对→qB暂停添加） |
| `mteam_api.py` | M-Team API 客户端 |
| `env_check.sh` | 环境变量完整性检查 |
| `connectivity_check.py` | 全服务连接测试（实际登录/API调用/站点可达性/Cookie保活） |
| `cookie_sync.py` | CookieCloud Cookie 同步（浏览器→secrets.env 自动更新） |
| `_cron_check.py` | Cron 进度检查（完成通知 + 死种告警 + 公开种自动清理） |

## 致谢

本技能在 PT 站适配过程中参考了以下优秀项目：
- [PT-depiler](https://github.com/) - NexusPHP 站点解析参考
- [MoviePilot](https://github.com/jxxghp/MoviePilot) - 部分功能设计灵感

## 许可

MIT
