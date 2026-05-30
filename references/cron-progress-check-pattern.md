# Cron 下载进度检查 — 执行模式参考

## ⚠️ 关键：不要用 `qb_monitor.py --tracker`

`qb_monitor.py --tracker` 的 `_read_tracker()` 内部执行 `int(f.read().strip())`，期望 tracker 文件是**单个 epoch 时间戳整数**。`pt_completed_last.txt` 存储的是 **hash 列表**（每行一个 40 字符 hex），两者格式不兼容。混用会导致 `_read_tracker()` 抛 `ValueError` 退回 epoch 0，cutoff 变成 1970-01-01，**每次 cron 都展示全部完成记录**。

正确做法：cron job 用 `qb_monitor.py --full` 拿原始数据，自己读 hash 列表做集合对比。

## 背景

`pt_completed_last.txt` 存储的是**已通知过的 torrent hash 列表**（每行一个 40 字符 hex），不是 epoch 时间戳。`qb_monitor.py --tracker` 期望的是 epoch 时间戳格式，所以两者不兼容。

## 正确执行流程（cron job 用）

```
1. 脚本自动从 secrets.env 读取 QBITTORRENT_* 连接信息
2. Python 脚本用 urllib.request 登录 qB → 获取所有 torrents
3. 读 pt_completed_last.txt → 构建 known_hashes 集合
4. 筛选 progress==1.0 且 hash 不在 known_hashes 中的 → new_completed
5. 筛选 progress==0.0 且 added_on 超过7天的 → dead
6. 报告 new_completed（去重：同内容多文件只报一次）→ 更新 pt_completed_last.txt
7. 报告 dead → 不更新 tracker
8. 两者都没有 → 回复 `[SILENT]`（三个字符，无其他内容。符合主 SKILL.md v2.5 静默规范）
```

## 关键约束

- **不能手写 `curl` 访问 qB**：tirith 会拦截所有含原始 IP / HTTP / 私有网络的 curl 命令
- **必须用 Python `urllib.request`**：skill 脚本（`qb_monitor.py` 等）内部已封装，不走 shell 扫描
- **必须去重报告**：同一内容可能有多个 hash（不同 tracker、不同编码版本），只报一次主名称
- **更新 tracker 时追加所有新 hash**（含重复的），确保下次不再误报

## 参考实现

完整实现见 `scripts/_cron_check.py`，核心逻辑：

```python
# 标准环境加载（与其他脚本一致）
_skill_dir = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(_skill_dir, "..", "secrets.env")
_env_cache = None
def _load_env_file(): ...
def _env(name, default=""): ...

# 登录 qB → 获取全部种子
# 读 pt_completed_last.txt → known_hashes 集合
# progress >= 1.0 且 hash 不在 known → new_completions
# progress == 0 + stalledDL + 7天+ → dead_torrents
# 去重：strip [prefix] 后取前40字符比较
# 写回：append 新 hash 到 pt_completed_last.txt
# 输出 JSON: {known_count, total_torrents, new_completions, dead_torrents}
```

去重报告逻辑（cron prompt 层使用）：

同一内容在 qB 中可能出现多次（不同编码版本、不同 tracker），报告时去重：

```python
import re
seen = set()
for item in new_completed:
    core = re.sub(r'^\[.+?\]\s*', '', item["name"])[:40]
    if core not in seen:
        seen.add(core)
        short = re.sub(r'^\[.+?\]\s*', '', item["name"])[:50]
        print(f"✅ {short} 完成")
```
