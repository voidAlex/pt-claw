# Cron 定时任务模式参考

## 下载进度检查

### ⚠️ 关键：不要用 `qb_monitor.py --tracker`

`qb_monitor.py --tracker` 的 `_read_tracker()` 内部执行 `int(f.read().strip())`，期望 tracker 文件是**单个 epoch 时间戳整数**。`pt_completed_last.txt` 存储的是 **hash 列表**（每行一个 40 字符 hex），两者格式不兼容。混用会导致 `_read_tracker()` 抛 `ValueError` 退回 epoch 0，cutoff 变成 1970-01-01，**每次 cron 都展示全部完成记录**。

正确做法：cron job 用 `qb_monitor.py --full` 拿原始数据，自己读 hash 列表做集合对比。

### 背景

`pt_completed_last.txt` 存储的是**已通知过的 torrent hash 列表**（每行一个 40 字符 hex），不是 epoch 时间戳。`qb_monitor.py --tracker` 期望的是 epoch 时间戳格式，所以两者不兼容。

### 正确执行流程（cron job 用）

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

### 通知类型

| type | icon | 说明 |
|------|------|------|
| `completion` | ✅ | 新完成的下载（去重后） |
| `dead_reminder` | 💀 | 死种告警，含 `remind_count` 和 `action_hint` |
| `auto_cleaned` | 🧹 | 已自动备份并移除的公开磁链 |

### 死种通知频率控制

`pt_notify_state.json`（schema 见 `templates/pt_notify_state.example.json`）追踪每个死种的通知状态：

- **首次发现**：立即通知，`notify_count=1`
- **后续提醒**：距 `last_notified` 超过 `dead_interval_hours`（默认 6h）且 `notify_count < dead_max_reminders`（默认 20）时再次提醒
- **自动清理**：死种恢复下载或被删除后，记录自动移除

### 关键约束

- **不能手写 `curl` 访问 qB**：tirith 会拦截所有含原始 IP / HTTP / 私有网络的 curl 命令
- **必须用 Python `urllib.request`**：skill 脚本（`_cron_check.py` 等）内部已封装，不走 shell 扫描
- **必须去重报告**：同一内容可能有多个 hash（不同 tracker、不同编码版本），只报一次主名称
- **更新 tracker 时追加所有新 hash**（含重复的），确保下次不再误报
- **`pt_notify_state.json` 不要删除**：丢失会导致通知计数重置，用户会被重复提醒

### 参考实现

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

## 成人追剧优化链路

Cron 自动追剧处理成人演员关注时的优化链路。适用于定时任务场景（无用户交互，需快速完成）。

### 背景

实测发现：
- PTTime/M-Team 成人区搜索 SONE/SNOS/FNS 等新番号系列 **全部返回 0 结果**
- 每部单独调 `pt_search.py --adult` 浪费 8 站 × 20 次 API 调用，耗时且无产出
- Sukebei Nyaa 对番号覆盖率高，做种数可直接判断活性

### 推荐链路（Cron 模式）

```
JavBus/javbus-api 获取片单
  → download_history filter（本地 JSON，毫秒级）
  → JF1 API 去重（按番号逐条查）
  → PT 搜索 ❌ 跳过（成人番号几乎无结果）
  → Sukebei Nyaa 批量搜索（Python 脚本，代理直连）
  → 按做种数排序 → qb_add.py 批量推送
  → download_history 记录
```

### 对比

| 步骤 | 原流程（交互模式） | Cron 优化模式 |
|------|-----------------|-------------|
| 元数据 | JavBus 裸爬或 star 页 | **javbus-api** `/api/movies/search?keyword=` |
| PT 搜索 | pt_search.py --adult（每部） | **跳过** |
| 公开源 | 按需回退 | **直接 Sukebei**，一次性批量 |
| Push | 逐部确认路径 | 批量 stdin JSON，统一 category/tags |

### javbus-api 关键端点

部署后（`docker run -d -p 8922:3000 ovnrain/javbus-api`）：

```
GET /api/movies/search?keyword=<演员名>&page=1&magnets=filter
```

- 支持中文名搜索（如 `浅野`、`浅野こころ`）
- 返回分页，每页 30 条
- 自动过滤无关结果（同名不同人会被聚合）
- 比裸爬快 10x，无需处理 Cloudflare

### Sukebei 批量搜索 Python 模板

```python
import urllib.request, urllib.parse
from xml.etree import ElementTree as ET

PROXY = "<PROXY_HOST>"
SUKEBEI_RSS = "https://sukebei.nyaa.si/?page=rss"
NYAA_NS = "https://sukebei.nyaa.si/xmlns/nyaa"

proxy_handler = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
opener = urllib.request.build_opener(proxy_handler)
opener.addheaders = [("User-Agent", "Mozilla/5.0")]

def search_sukebei(code):
    url = f"{SUKEBEI_RSS}&q={urllib.parse.quote(code)}"
    req = urllib.request.Request(url)
    with opener.open(req, timeout=20) as resp:
        root = ET.fromstring(resp.read().decode())
    results = []
    for item in root.findall(".//item"):
        title = item.find("title").text
        seeders = int(item.find(f"{{{NYAA_NS}}}seeders").text or 0)
        ih = item.find(f"{{{NYAA_NS}}}infoHash").text
        results.append({"title": title, "seeders": seeders, "hash": ih})
    results.sort(key=lambda x: x["seeders"], reverse=True)
    return results
```

### qB 批量推送注意事项

- `qb_add.py --stdin` 读取 JSON 行
- `"Fails."` 响应 = 种子已存在，不是错误 → 补打标签即可
- 所有公开磁链必须 `"video_only": true` + `"tags": ["sukebei"]`
- 推送后立即调用 `download_history.py add` 记录

### 演员名歧义处理

用户关注名可能不精确（如「浅野心」可能指 浅野こころ 或 浅野心愛）。策略：
1. 用 javbus-api 搜演员名，获取所有匹配结果
2. 按作品数量和知名度判断主次（S1 专属 > FALENO 新人）
3. 在报告中标注两位演员的来源（如「浅野こころ 46部 + 浅野心愛 10部」）
4. Cron 无用户交互 → 全部纳入下载候选，由 JF1 和下载历史去重
