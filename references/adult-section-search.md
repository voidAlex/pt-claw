# PTTime / M-Team 成人区（9kg）搜索适配

## PTTime

- **页面**: `https://www.pttime.org/adults.php`
- **搜索参数**:
  - **按标题**: `searchstr=` — 匹配种子标题文本
  - **按演员**: `actor=` — 匹配演员标签（演员名以 tag 形式存在于 HTML 中，不在标题里，必须用 `actor=` 才能命中）
- **URL 格式**: `https://www.pttime.org/adults.php?searchstr=<关键词>` 或 `adults.php?actor=<演员名>`
- **HTML 结构**: 与主页 `torrents.php` 相同（NexusPHP 双行结构），解析器通用
- **下载链接**: 与主页格式一致 `download.php?id=XXX&passkey=YYY&uid=ZZZ`
- **演员标签格式**: `<a class='dib cp' href='/adults.php?actor=演员名'><span class='tags'>演员名</span></a>`
- **网络**: 直连 SSL 握手可能超时，建议走代理

### 搜索模式对比

| 搜索类型 | 参数 | 命中范围 | 示例 |
|---------|------|---------|------|
| 按番号 | `searchstr=SSIS-448` | 标题含 SSIS-448 | 精确匹配番号 |
| 按演员 | `actor=浅野心` | 所有该演员作品 | 按标签过滤，命中率高 |
| 按关键词 | `searchstr=4K` | 标题含 4K | 宽泛匹配，噪音大 |

**重要**: 搜索演员不能用 `searchstr=`（演员名通常在 tag 里不在标题里），必须用 `actor=`。

### URL 编码

中文参数必须 URL 编码。curl 示例：
```bash
curl -s --data-urlencode "actor=浅野心" "https://www.pttime.org/adults.php" -G -b "cookie_str"
```

## M-Team (馒头)

- **Web 页面**: `https://kp.m-team.cc/browse/adult`
- **搜索**: 需 cookie 认证（当前未获取 mteam web cookie，依赖 API）
- **API 搜索**: 待验证是否支持 `mode: "adult"` 或 `categories` 参数
- **API 限速**: 1000 次/24h，超限返回 403
- **当前状态**: API 搜索基本不限分类即搜全站，成人内容是否被过滤待 API 恢复后验证

## 脚本适配建议

在 `pt_search.py` 中为 `pttime` 站点增加 `adult_mode` 和 `actor` 参数：

```python
# Adult mode: use adults.php
if adult_mode:
    if actor:
        url = f"{site['url']}/adults.php?actor={urllib.parse.quote(actor)}"
    else:
        url = f"{site['url']}/adults.php?searchstr={urllib.parse.quote(query)}"
else:
    url = f"{site['url']}/torrents.php?search={urllib.parse.quote(query)}&notnewword=1"
```

两个页面的 HTML 解析逻辑完全相同，无需额外 parser。
