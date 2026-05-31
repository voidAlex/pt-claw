# Site Tags — 站点标签映射

推送种子到 qBittorrent 时必须打来源标签（`--tags`）。标签 = 站点 ID（小写）。

## 核心站

| 来源 | 标签 | 来源 | 标签 |
|------|------|------|------|
| M-Team | `mteam` | CarPT | `carpt` |
| PTTime | `pttime` | HDFans | `hdfans` |
| BTSchool | `btschool` | 1PTBar | `1ptba` |
| SoulVoice | `soulvoice` | 织梦 | `zmpt` |
| PTSkit | `ptskit` | PTHome | `pthome` |
| HDSky | `hdsky` | HDHome | `hdhome` |
| Audiences | `audiences` | KeepFriends | `keepfrds` |
| ToTheGlory | `ttg` | Sukebei | `sukebei` |

## 扩展站

| 来源 | 标签 | 来源 | 标签 |
|------|------|------|------|
| 13城 | `13city` | 52Movie | `52movie` |
| 52PT | `52pt` | Afun | `afun` |
| AGSVPT | `agsvpt` | alingPT | `alingpt` |
| 梓喵 | `azusa` | 包子 | `baozi` |
| 北邮人 | `byrbt` | 藏宝阁 | `cbg` |
| 传道院 | `cdy` | CHDBits | `chdbits` |
| 蟹黄堡 | `crabpt` | 财神 | `cspt` |
| 大青虫 | `cyanbug` | 碟粉 | `discfan` |
| 龍之家 | `dragonhd` | DepthStudio | `dstudio` |
| 天枢 | `dubhe` | 自由农场 | `freefarm` |
| GGPT | `ggpt` | 海胆 | `haidan` |
| HDArea | `hdarea` | HDBao | `hdbao` |
| 天使 | `hdcity` | HDClone | `hdclone` |
| HDDolby | `hddolby` | HDKylin | `hdkylin` |
| HDTime | `hdtime` | HDU | `hdupt` |
| HDVideo | `hdvideo` | 憨憨 | `hhanclub` |
| 百川PT | `hitpt` | 海棠 | `htpt` |
| 蝴蝶 | `hudbt` | 好学 | `hxpt` |
| 爱萝莉 | `ilolicon` | PT分享站 | `itzmx` |
| JoyHD | `joyhd` | 龟站 | `kamept` |
| Kelu | `kelu` | 库非 | `kufei` |
| 昆仑 | `kunlun` | 垃圾堆 | `lajidui` |
| 柠檬不甜 | `lemonhdnet` | 龙PT | `longpt` |
| LuckPT | `luckpt` | 三月传媒 | `march` |
| 瞬间 | `momentpt` | 音乐乌托邦 | `musopia` |
| 慕雪阁 | `muxuege` | MyPT | `mypt` |
| 南洋PT | `nanyangpt` | NexusHD | `nexushd` |
| NicePT | `nicept` | 浦园 | `njtupt` |
| NovaHD | `novahd` | OKPT | `okpt` |
| 皇后 | `opencd` | 奥申 | `oshenpt` |
| OurBits | `ourbits` | 熊猫 | `pandapt` |
| Piggo | `piggo` | PlayLet | `playletpt` |
| 咖啡 | `ptcafe` | PTer | `pter` |
| PTFans | `ptfans` | PTGTK | `ptgtk` |
| PTLAO | `ptlao` | PTLGS | `ptlgs` |
| 超科学喵 | `ptneko` | 烧包 | `ptsbao` |
| PTZONE | `ptzone` | RailgunPT | `railgunpt` |
| 雨 | `raingfh` | RetroFlix | `retroflix` |
| 肉丝 | `rousi` | 睿思 | `rs` |
| SBPT | `sbpt` | 下水道 | `sewerpt` |
| 思齐 | `siqi` | 葡萄 | `sjtu` |
| 春天 | `springsunday` | 阳光 | `sunnypt` |
| 躺平 | `tangpt` | TCCF | `tccf` |
| 太乙 | `tey` | 北洋 | `tjupt` |
| TLF | `tlfbits` | 唐门 | `tmpt` |
| TorrentHub | `torrenthub` | TU88 | `tu88` |
| U2 | `u2` | UBits | `ubits` |
| UltraHD | `ultrahd` | 冬樱 | `wintersakura` |
| 杏坛 | `xingtan` | 星陨阁 | `xingyunge` |
| 樱花 | `yinguskg` | ZRPT | `zrpt` |

## 用法

```bash
# qb_add.py 推送时指定标签
python3 scripts/qb_add.py "https://..." --tags pttime

# 也可用 qB API 手动打标签
curl -b <cookie> -X POST '<qb_url>/api/v2/torrents/addTags' \
  --data-urlencode "hashes=$HASH" --data-urlencode "tags=pttime"
```
