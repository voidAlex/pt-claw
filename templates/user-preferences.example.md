# 用户偏好配置

> **说明**：这是配置模板（`.example.md`）。首次使用 pt-claw 时，Agent 会读取此模板逐项确认，用真实值替换占位符后保存为 `user-preferences.md`（不入 Git）。敏感值（API key、密码、IP）写入 `~/.hermes/.env`。**不写入 memory**（容量有限，偏好配置全部走文件）。

## 下载偏好
- 编码优先：HEVC/H.265
- 清晰度优先：4K (2160p)

## 成人内容
- PT 做种阈值：≥5
- 版本优选：做种数 > 去码 > 字幕 > 画质
- 公开源优先级：JavBus > Sukebei

## qBittorrent 分类映射
- 电影 → /<MOVIE_PATH>
- 电视剧 → /<TV_PATH>
- 纪录片 → /<LIVE_PATH>
- 成人 → /<ADULT_PATH>

## 通知偏好
- 无事件时静默（[SILENT]）
- 下载完成通知 ✅
- 死种告警 💀

## Jellyfin 集成
- 实例数量：<COUNT>（如 2 个：成人 + 影视）
- JF1（成人）：地址和 API Key 见 `~/.hermes/.env` → `JELLYFIN1_URL` / `JELLYFIN1_API_KEY`
- JF2（影视）：地址和 API Key 见 `~/.hermes/.env` → `JELLYFIN2_URL` / `JELLYFIN2_API_KEY`
- 用途：自动去重 + 片库统计
- 未配置也不影响 PT 下载，仅跳过 JF 去重检查

## javbus-api（Docker）
- 部署地址：见 `~/.hermes/.env` → `JAVBUS_API_URL`
- 端口映射：`-p 8922:3000`
- 代理：通过 Docker daemon proxy 配置（`/etc/systemd/system/docker.service.d/proxy.conf`）
- 用途：封面预览 + 结构化磁链（含 HD/字幕/去码标记）
- ⚠️ 不部署也可裸爬 JavBus，仅数据不如 API 结构化

## 代理规则
- 默认：直连，不加代理
- 代理地址：见 `~/.hermes/.env` → `PT_PROXY`
- 需要代理的站：织梦（zmpt.cc）、PTTime（Cloudflare 盾）、JavBus
- 直连即可的站：BTSchool、CarPT、HDFans、SoulVoice
- ⚠️ 禁止无脑给所有请求加代理，代理 IP 可能被 PT 站封禁

## 代码偏好
- 所有代码任务委托 OpenCode (GLM-5.1)
- 禁止 /tmp 临时脚本
