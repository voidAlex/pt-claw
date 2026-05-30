# 用户偏好配置

> **说明**：这是配置模板（`.example.md`）。首次使用 pt-claw 时，Agent 会读取此模板逐项确认，用真实值替换占位符后保存为 `user-preferences.md`（不入 Git）。敏感值（API key、密码、IP）写入 `secrets.env`。**不写入 memory**（容量有限，偏好配置全部走文件）。

## 下载偏好
- 编码优先：HEVC/H.265
- 清晰度优先：4K (2160p)

## 成人内容
- 启用：<ENABLED>（true/false，初始化时用户确认）
- PT 做种阈值：≥5
- 版本优选：做种数 > 去码 > 字幕 > 画质
- 公开源优先级：JavBus > Sukebei
- 清晰度范围：<RESOLUTION_RANGE>（如：4K + 1080p 都接受）
- 默认下载路径：<ADULT_PATH>（如：分类 9kg → /9kg/x64/javdb-top250）

## qBittorrent 分类映射
- 电影 → 分类"电影" → /<MOVIE_PATH>
- 电视剧 → 分类"电视剧" → /<TV_PATH>
- 纪录片 → 分类"纪录片" → /<LIVE_PATH>
- 综艺/节目 → 分类"<SHOW_TAG>" → /<SHOW_PATH>
- 成人 → 分类"<ADULT_TAG>" → /<ADULT_PATH>
- 其他 → 分类"<OTHER_TAG>" → /<OTHER_PATH>

## 通知偏好
- 无事件时静默（[SILENT]）
- 下载完成通知 ✅
- 死种告警 💀
- 定时任务只推必要信息，不推送进度百分比/做种数/汇总统计等废话

## Jellyfin 集成
- 实例数量：<COUNT>（如 2 个：成人 + 影视）
- JF1（成人）：地址和 API Key 见 `secrets.env` → `JELLYFIN1_URL` / `JELLYFIN1_API_KEY`
- JF2（影视）：地址和 API Key 见 `secrets.env` → `JELLYFIN2_URL` / `JELLYFIN2_API_KEY`
- 用途：自动去重 + 片库统计
- 未配置也不影响 PT 下载，仅跳过 JF 去重检查

## javbus-api（Docker）
- 部署地址：见 `secrets.env` → `JAVBUS_API_URL`
- 端口映射：`-p 8922:3000`
- 代理：通过容器环境变量 `HTTP_PROXY`/`HTTPS_PROXY` 传入（同 `PT_PROXY` 值，见 `docker-compose.javbus-api.yml`）
- 用途：封面预览 + 结构化磁链（含 HD/字幕/去码标记）
- ⚠️ 不部署也可裸爬 JavBus，仅数据不如 API 结构化

## 代理规则
- 默认：直连，不加代理
- 代理地址：见 `secrets.env` → `PT_PROXY`
- 需要代理的站：M-Team（馒头 API）、织梦（zmpt.cc）、BTSchool、CarPT、SoulVoice、JavBus
- 直连即可的站：PTTime、HDFans、1PTBar
- ⚠️ 禁止无脑给所有请求加代理，代理 IP 可能被 PT 站封禁

## 其他偏好
- 原盘/压制偏好：<REMUX_OR_ENCODE>（如：优先原盘 REMUX，次选压制版）
- 字幕语言：<SUBTITLE_LANG>（如：简体中文 > 繁体中文 > 原声无字幕）
- 音轨偏好：<AUDIO_PREF>（如：优先 Atmos/DTS:X，次选 DTS-HD MA）
- 制作组偏好：<RELEASE_GROUP>（如：优先 FraMeSToR、PTHome，排除 <EXCLUDED_GROUPS>）

## 代码偏好
- 所有写代码/改代码任务委托 OpenCode CLI，使用 <MODEL> 模型
- 禁止自己直接写代码或调 patch/write_file 改脚本
- 禁止 /tmp 临时脚本，日常用 skill 脚本

## 站点标签
推送到 qB 必打来源标签：<SITE_TAGS>（如：mteam / pttime / btschool / carpt / hdfans / 1ptba / soulvoice / zmpt / sukebei / javbus）

## 下载确认闸门
- 搜索只展示信息，等用户说「下」才推送
- 删除只 `--check` 预览，等用户说「清了」才执行
- 删除前自动备份 .torrent + 元数据到 `torrent_backups/` 和 `pt_deleted_backup.json`
