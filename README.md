# pt-claw

多站 PT 种子搜索与下载技能，兼容任意 AI Agent。

对话式搜索 12 个 PT 站资源、推送到 qBittorrent、监控下载进度——全程纯脚本，无 Prowlarr/Jackett 依赖。

## 功能

- **12 站支持**：M-Team (API)、PTTime、BTSchool、CarPT、HDFans、1PTBar、SoulVoice、织梦、PTSkit、PTHome、HDSky、HDHome
- **双引擎搜索**：Cookie 直连站点 + M-Team REST API
- **智能去重**：下载历史记录 + Jellyfin 片库感知，删了的内容不会重复下载
- **自动回退**：PT 做种不足时自动回退到公开磁链
- **站点标签**：每次下载自动打上来源标签（mteam/pttime/sukebei 等）
- **定时任务**：进度监控+公开种清理(15m)、每日追剧(10:00)、Cookie同步/保活(视配置)
- **刷流保号**：可选 Freeleech 自动辅种

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
```

脚本是 Agent 内部调用的，使用者无需关心命令行参数。

## 环境要求

- Python 3.10+
- `cryptography`（CookieCloud 同步需要：`pip install cryptography`）
- qBittorrent Web UI 已开启
- PT 站 Cookie（存于 `secrets.env`）
- M-Team API Key（可选，API 搜索需要）

## 配置

首次使用时，Agent 会交互式引导配置。参考 `templates/secrets.env.example` 了解所需环境变量。

## 脚本清单

| 脚本 | 用途 |
|------|------|
| `pt_search.py` | 多站搜索（NexusPHP + M-Team API） |
| `qb_add.py` | 添加种子到 qBittorrent（含站点标签+正片提取） |
| `qb_monitor.py` | qB 全功能查询（状态/过滤/删除） |
| `qb_public_cleanup.py` | 公开磁链清理（手动使用，cron 已合并到 `_cron_check.py`） |
| `qb_restore.py` | 删种恢复（从备份还原到 qB） |
| `qb_backup.py` | 删种前自动备份元数据 |
| `sukebei_search.py` | Sukebei 公开磁链搜索 |
| `javbus_magnet.py` | JavBus 磁链爬取 |
| `javbus_star.py` | 演员片单交叉对比（javbus-api → JF + 历史） |
| `jf_query.py` | Jellyfin 查询（演员排名/搜索/去重） |
| `download_history.py` | 下载历史追踪（防重复） |
| `pt_ratio_boost.py` | Freeleech 自动辅种 |
| `cross_seed.py` | 多站辅种验证与推送（下载.torrent→SHA1比对→qB暂停添加） |
| `mteam_api.py` | M-Team API 客户端 |
| `env_check.sh` | 环境变量完整性检查 |
| `connectivity_check.py` | 全服务连接测试（实际登录/API调用/站点可达性/Cookie保活） |
| `cookie_sync.py` | CookieCloud Cookie 同步（浏览器→secrets.env 自动更新） |
| `_cron_check.py` | Cron 进度检查（完成通知 + 死种告警 + 公开种自动清理） |
| `_check_stalled.py` | 死种诊断（检查停滞种子时长/进度） |

## 许可

MIT
