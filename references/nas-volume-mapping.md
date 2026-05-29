# NAS Volume Mapping for qBittorrent Recovery

## Container → Host path mapping

When recovering torrents from disk, map NFS mount paths to qBittorrent Docker container paths:

| NFS mount (on Hermes host) | qB container path | Content |
|---|---|---|
| `<NAS_MOUNT_MEDIA>/video/movie` | `/media/video/movie` | 电影 |
| `<NAS_MOUNT_MEDIA>/video/tv` | `/media/video/tv` | 电视剧 |
| `<NAS_MOUNT_MEDIA>/video/live` | `/media/video/live` | 纪录片 |
| `<NAS_MOUNT_MEDIA>/video/show` | `/media/video/show` | 综艺 |
| `<NAS_MOUNT_MEDIA>/video/sport` | `/media/video/sport` | 体育 |
| `<NAS_MOUNT_MEDIA>/video/music-live` | `/media/video/music-live` | 音乐现场 |
| `<NAS_MOUNT_DOWNLOADS>` | `/downloads` | qB 默认下载路径 |
| `<NAS_ADULT_PATH>/javdb-top250` | `<QB_ADULT_PATH>` | 成人内容 |
| `<NAS_ADULT_PATH>/其他` | `<QB_ADULT_OTHER_PATH>` | 其他成人（公开源）⚠️ SKIP |
| `<NAS_MOUNT_QB>/config` | `/config` | qB 配置目录 |
| `<NAS_MOUNT_QB>/config/qBittorrent/BT_backup` | — | .torrent 备份文件 |

## NAS NFS mount commands

```bash
sudo mount -t nfs <NAS_IP>:/<VOL_MEDIA> <NAS_MOUNT_MEDIA>
sudo mount -t nfs <NAS_IP>:/<VOL_DOWNLOADS> <NAS_MOUNT_DOWNLOADS>
sudo mount -t nfs <NAS_IP>:/<VOL_SYSTEM> <NAS_MOUNT_SYSTEM>
sudo mount -t nfs <NAS_IP>:/<VOL_DOCKER> <NAS_MOUNT_QB>
```

## Import path rule

When importing .torrent files with `savepath`, use the **container path** (right column), not the NFS path. Multipart upload ignores `?savepath=` query param — always follow with `setLocation` API call.

## Tiered recovery

1. **Local .torrent files** — scan data directories for `.torrent` siblings, import with correct container path
2. **PT snatchlist** — user re-downloads original .torrent from PT site download history (guaranteed exact match)
3. **PT site search** — last resort; .torrent internal structure may not match disk. Always verify after import that qB is checking existing files, NOT re-downloading
4. **Public content** — skip PT recovery, these were magnet links from public sources
