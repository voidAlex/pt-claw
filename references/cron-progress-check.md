# Cron 下载进度检查 — 进度监控 + 公开种清理 + 死种告警

## ⚠️ 关键：不要用 `qb_monitor.py --tracker`

`qb_monitor.py --tracker` 的 `_read_tracker()` 内部执行 `int(f.read().strip())`，期望 tracker 文件是**单个 epoch 时间戳整数**。`pt_completed_last.txt` 存储的是 **hash 列表**（每行一个 40 字符 hex），两者格式不兼容。混用会导致 `_read_tracker()` 抛 `ValueError` 退回 epoch 0，cutoff 变成 1970-01-01，**每次 cron 都展示全部完成记录**。

正确做法：cron job 用 `qb_monitor.py --full` 拿原始数据，自己读 hash 列表做集合对比。

## 背景

`pt_completed_last.txt` 存储的是**已通知过的 torrent hash 列表**（每行一个 40 字符 hex），不是 epoch 时间戳。`qb_monitor.py --tracker` 期望的是 epoch 时间戳格式，所以两者不兼容。

## 正确执行流程（cron job 用）

`_cron_check.py` 合并了进度检查 + 公开种清理 + 死种频率控制，一次执行完成全部检查：

```
1. 脚本自动从 secrets.env 读取 QBITTORRENT_* 连接信息
2. Python 脚本用 urllib.request 登录 qB → 获取所有 torrents
3. 读 pt_completed_last.txt → 构建 known_hashes 集合
4. 读 pt_notify_state.json → 加载死种通知状态（频率控制）
5. 筛选 progress==1.0 且 hash 不在 known_hashes 中的 → new_completed
   - 公开磁链（sukebei/javbus 标签）且已完成 → 自动备份+移除（不通知用户）
   - 公开种占比超 20% 时跳过清理（安全防线）
6. 筛选 progress==0 + stalledDL + 7天+ → dead
   - 首次发现 → 立即通知
   - 已知死种 → 检查距上次通知是否超 6h + 未达 max_reminders(20) → 决定是否再次提醒
7. 清理已恢复的死种记录（不在当前 dead 列表中的旧记录）
8. 更新 pt_completed_last.txt（追加新 hash）
9. 更新 pt_notify_state.json（保存通知计数和时间戳）
10. 输出 JSON:
    - 无事件 → {"silent": true}
    - 有事件 → {"notifications": [...], "silenced": {"dead": N}, "stats": {...}}
```

## 通知类型

| type | icon | 说明 |
|------|------|------|
| `completion` | ✅ | 新完成的下载（去重后） |
| `dead_reminder` | 💀 | 死种告警，含 `remind_count` 和 `action_hint` |
| `auto_cleaned` | 🧹 | 已自动备份并移除的公开磁链 |

## 死种通知频率控制

`pt_notify_state.json`（schema 见 `templates/pt_notify_state.example.json`）追踪每个死种的通知状态：

- **首次发现**：立即通知，`notify_count=1`
- **后续提醒**：距 `last_notified` 超过 `dead_interval_hours`（默认 6h）且 `notify_count < dead_max_reminders`（默认 20）时再次提醒
- **自动清理**：死种恢复下载或被删除后，记录自动移除

## Cron 输出截断预防（致命级）

**现象**：Cron 运行报错 `RuntimeError: Response truncated due to output length limit`，用户收不到通知。

**根因**：cron job 用 `skills=["pt-claw"]` 会把整份 SKILL.md（~20KB）内联到每次运行的上下文。光 skill 文本就占 ~25KB 输出。之前没事是因为脚本返回 silent（agent 只回 `[SILENT]` 刚好在限制内），一旦有实际通知要格式化，总响应超出上限被截断。

**修复（两件套，同时执行）**：
1. **Cron job 不要用 `skills=["pt-claw"]`**。改用自包含 prompt（workdir 已指向 skill 目录，脚本直接可用）：`prompt="工作目录已设为 pt-claw 项目根目录，secrets.env 和 scripts/ 均可用。运行 \`python3 scripts/_cron_check.py\`..."`，`skills=[]`
2. **拉满输出上限**：`hermes config set model.max_tokens 32768`（代码硬上限，见下方说明）

Hermes max_tokens 机制（便于排查同类问题）：
- 来源：`config.yaml` → `model.max_tokens` → `agent.max_tokens`（`agent/agent_init.py:1264`）
- 默认值：None（provider 默认），截断重试时以 4096 为基准
- 截断重试：response finish_reason="length" 时，agent 最多重试 3 次，每次 boost = base × (重试次数+1)（第1次 2×，第2次 3×），**上限 min(boost, 32768)**
- 3 次重试后仍截断 → 返回 `"error": "Response truncated due to output length limit"`
- 生效位置：`chat_completions.py:286-301`，优先级 ephemeral > max_tokens；DeepSeek 等非 OpenAI provider 映射为 `{"max_tokens": N}` 参数

## 关键约束

- **不能手写 `curl` 访问 qB**：tirith 会拦截所有含原始 IP / HTTP / 私有网络的 curl 命令
- **必须用 Python `urllib.request`**：skill 脚本（`_cron_check.py` 等）内部已封装，不走 shell 扫描
- **必须去重报告**：同一内容可能有多个 hash（不同 tracker、不同编码版本），只报一次主名称
- **更新 tracker 时追加所有新 hash**（含重复的），确保下次不再误报
- **`pt_notify_state.json` 不要删除**：丢失会导致通知计数重置，用户会被重复提醒

## 参考实现

完整实现见 `scripts/_cron_check.py`，核心逻辑：

```python
# 标准环境加载（与其他脚本一致）
_skill_dir = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(_skill_dir, "..", "secrets.env")
_env_cache = None
def _load_env_file(): ...
def _env(name, default=""): ...

# 通知状态管理（pt_notify_state.json）
def _load_state(): ...     # dead_torrents + notify_config
def _save_state(state): ... # fcntl 锁写入

# 登录 qB → 获取全部种子
# 读 pt_completed_last.txt → known_hashes 集合
# progress >= 1.0 且 hash 不在 known → new_completions
# progress == 0 + stalledDL + 7天+ → dead（频率控制：6h间隔，最多20次）
# 公开磁链(sukebei/javbus)已完成 → 自动备份+移除（占比>20%跳过）
# 去重：strip [prefix] 后取前40字符比较
# 写回：append 新 hash 到 pt_completed_last.txt，更新 pt_notify_state.json
# 输出 JSON: {"notifications": [...], "silenced": {"dead": N}, "stats": {...}} 或 {"silent": true}
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
