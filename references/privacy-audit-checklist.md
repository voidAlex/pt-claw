# 隐私审计检查清单

## 适用场景

用户执行 `skill_manage` 推送前、或质疑"有没有硬编码隐私"时，按此清单做全量审计。

## 审计步骤

### 1. 扫描硬编码凭据

```bash
# UUID格式的API Key
grep -rnP '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}' . \
  --include='*.py' --include='*.md' --include='*.sh' --include='*.json'

# 常见key/token字段
grep -rnP '(api_key|api_token|apikey|passkey|secret)\s*=\s*["'"'"'][a-zA-Z0-9]' . \
  --include='*.py' --include='*.md' --include='*.sh'
```

### 2. 扫描内网IP

```bash
grep -rnP '10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}' . \
  --include='*.py' --include='*.md' --include='*.sh' --include='*.json'
```

### 3. 扫描个人身份信息

```bash
# 中文姓名（3-4字）
grep -rnP '[\x{4e00}-\x{9fa5}]{2,4}' *.md | grep -v '脚本\|技能\|配置\|触发'

# 邮箱
grep -rnP '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' .

# 手机号
grep -rnP '1[3-9]\d{9}' .

# 用户ID
grep -rnP '\b\d{5,8}\b' references/*.md
```

### 4. 扫描路径泄露

```bash
# NAS路径
grep -rnP '/mnt/nas-|/volume\d+/|/MacOS/' .

# 用户家目录  
grep -rnP '/home/\w+/[^.hermes]' .

# 特定内容路径名（javdb-top250、9kg等自定义目录）
grep -rnP 'javdb|9kg|MacOS' .
```

### 5. 扫描Cookie/Token片段

```bash
grep -rnP 'c_secure_uid|c_secure_pass|cookie.*[a-f0-9]{20,}' . --include='*.md' --include='*.py'
```

## 替换规则

| 发现内容 | 替换为 | 说明 |
|---------|--------|------|
| API Key/UUID | `MTEAM_API_KEY` 环境变量引用 | 绝对禁止硬编码 |
| 内网 IP | 占位符如 `<QB_HOST>`, `<NAS_IP>`, `<PROXY_HOST>` | 私有地址也不可暴露 |
| 用户 ID | 删除或改为 `<USER_ID>` | 无文档价值 |
| NAS 路径 | `<NAS_MEDIA_PATH>`, `<NAS_ADULT_PATH>` | 保留结构，隐藏细节 |
| 自定义目录名 | 通用描述 | 如 `/9kg/→/<DOWNLOAD_CATEGORY>/` |
| 个人邮箱/手机 | 删除 | 无文档价值 |
| 成人内容站名 | 删除，改为通用描述 | 个人偏好信息 |

## 修复后验证

```bash
# 确认无残留（三项均为0）
echo "API Key:" && grep -rc '<pattern>' . --include='*.py' --include='*.md' | grep -v ':0$'
echo "IPs:" && grep -rnP '10\.\d{1,3}\.\d{1,3}\.\d{1,3}' .
echo "UserID:" && grep -rnP '<USER_ID>' .
```

## 独立第三方验证（必须！）

⚠️ **自己审自己会漏** — 本次审计中 Hermes 漏掉了 NAS NFS 挂载路径、容器侧 `/9kg/x64/*` 保留真实值、审计清单模板中残留真实用户 ID。OpenCode 独立审计全部发现。

修复完后必须让**独立的 coding agent**（OpenCode/Codex/Claude Code）做第三方审计：

```bash
opencode run '对 <repo> 做全量隐私审计。扫描API Key/UUID、内网IP、
个人身份信息（姓名/邮箱/手机/公司）、NAS路径、用户ID。逐文件报告。
已被<PLACEHOLDER>替代的不算问题。只报告含真实值的发现。'
```

或通过 Hermes 的 `delegate_task` 委托子 agent 做独立审计后再推送。独立验证是推送前的最后一道防线。

如果敏感信息已推送至 GitHub：

```bash
# 1. 立即 rotate 对应的 API Key/Token（控制台重新生成）
# 2. 用 filter-branch 重写历史
git filter-branch -f --tree-filter '
find . -type f -not -path "./.git/*" | while read f; do
  sed -i "s|<SENSITIVE_STRING>|<PLACEHOLDER>|g" "$f" 2>/dev/null
done
' -- --all

# 3. 清理备份 ref
git update-ref -d refs/original/refs/heads/main

# 4. 验证
git log -p --all | grep -c '<SENSITIVE_STRING>'  # 应为 0

# 5. 强制推送
git push --force --all
git push --force --tags
```

⚠️ `git filter-branch` 会改变所有 commit SHA，协作者需重新 clone。
