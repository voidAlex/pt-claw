# NexusPHP PT 站 HTML 解析架构

## 两种页面模式

### 模式 1: rowfollow 分离式（PTTime）

```html
<tr data=47540>                              ← 标题行（含 data 属性）
  <td>category icon</td>
  <td class="embedded">                      ← 嵌套 table
    <a title="Title">Title</a>
    50%免费
  </td>
</tr>
<td class="rowfollow dn">0</td>              ← 统计单元格（在标题 </tr> 之后）
<td class="rowfollow">41.57<br>GB</td>       ← 大小
<td class="rowfollow"><b><a>7</a></b></td>   ← 做种数
<td class="rowfollow">0</td>                 ← 下载数
<tr data=59817>                              ← 下一个种子的标题行
```

**解析策略**: `_parse_nexusphp()`
- 找 `<tr data=ID>` 匹配标题和 promo
- 标题行 `</tr>` 到下一个 `<tr data=` 之间是统计区
- 大小: `<td>N.NN<br>GB</td>` 
- 种子: `<b>N</b>`（第一个 = seeders，第二个 = leechers）

### 模式 2: 经典表格（BTSchool/CarPT/HDFans/1PTBar/SoulVoice/织梦）

```html
<table class="torrents">
  <tr><th>...</th></tr>                      ← 表头
  <tr>                                        ← 标题行（嵌套 table）
    <td class="embedded">
      <table class="torrentname">
        <tr>
          <td>
            <a title="Title">Title</a>
            50%免费
          </td>
        </tr>
      </table>
    </td>
    <td class="embedded">📥</td>              ← 下载图标
  </tr>
  ...stats cells between rows...              ← 同模式 1 的 stats 结构
  <tr>                                        ← 下一个标题行
```

**解析策略**: `_parse_nexusphp_classic()`
- ⚠️ 关键坑: `class="torrents"` 表内嵌套了内层 `<table>`，`</table>` 正则匹配会提前截断
- 解决方案: 不解析表格边界，直接用 download.php 链接定位
- 找每个 download.php 链接 → 向前找 `<tr` 开始 → 用深度计数找匹配 `</tr>`
- 标题在 `<a title="...">` 或 `details.php` 链接文本中
- Stats 在标题行 `</tr>` 和下一个 `<tr>` 之间（同模式 1）

## 通用规则

- 大小正则: `r'>\s*([\d.,]+)\s*(?:<br\s*/?>\s*)?(GB|MB|TB|KB)\s*<'`（处理 `<br>` 分隔）
- 种子数: stats 区第一个 `<b>N</b>` 通常是 seeders，第二个是 leechers
- Promo 检测: `halfdown`/`50%`/`pro_free` 在标题行 HTML 中
- 下载链接: 经典站无 passkey (`download.php?id=X`)，PTTime 有 passkey (`download.php?id=X&passkey=XX&uid=XX`)
