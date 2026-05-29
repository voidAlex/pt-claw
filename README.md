# pt-claw

多站 PT 种子搜索与下载技能，运行于 [Hermes Agent](https://hermes-agent.nousresearch.com)。

对话式搜索 8 个 PT 站资源、推送到 qBittorrent、监控下载进度——全程纯脚本，无 Prowlarr/Jackett 依赖。

## 功能

- **8 站支持**：M-Team (API)、PTTime、BTSchool、CarPT、HDFans、1PTBar、SoulVoice、织梦
- **双引擎搜索**：Cookie 直连站点 + M-Team REST API
- **智能去重**：下载历史记录 + Jellyfin 片库感知，删了的内容不会重复下载
- **自动回退**：PT 做种不足时自动回退到公开磁链
- **站点标签**：每次下载自动打上来源标签（mteam/pttime/sukebei 等）
- **定时任务**：进度监控(15m)、每日追剧(10:00)、公开种清理(30m)
- **刷流保号**：可选 Freeleech 自动辅种

## 使用方式

这是给 Hermes Agent 用的技能，加载后通过对话操作，不需要手动跑脚本。

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
- qBittorrent Web UI 已开启
- PT 站 Cookie（存于 `~/.hermes/.env`）
- M-Team API Key（可选，API 搜索需要）

## 配置

首次使用时，Hermes Agent 会交互式引导配置。参考 `.env.example` 了解所需环境变量。

## 脚本清单

| 脚本 | 用途 |
|------|------|
| `pt_search.py` | 多站搜索（NexusPHP + M-Team API） |
| `qb_add.py` | 添加种子到 qBittorrent（含站点标签+正片提取） |
| `qb_monitor.py` | qB 全功能查询（状态/过滤/删除） |
| `qb_public_cleanup.py` | 公开磁链自动清理 |
| `qb_restore.py` | 删种恢复（从备份还原到 qB） |
| `sukebei_search.py` | Sukebei 公开磁链搜索 |
| `javbus_magnet.py` | JavBus 磁链爬取 |
| `javbus_star.py` | 演员片单交叉对比（javbus-api → JF + 历史） |
| `jf_query.py` | Jellyfin 查询（演员排名/搜索/去重） |
| `download_history.py` | 下载历史追踪（防重复） |
| `pt_ratio_boost.py` | Freeleech 自动辅种 |
| `mteam_api.py` | M-Team API 客户端 |
| `env_check.sh` | 环境变量完整性检查 |
| `with_proxy.sh` | 代理包装脚本（按需使用） |

## 许可

MIT
