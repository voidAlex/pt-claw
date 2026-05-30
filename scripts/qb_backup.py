#!/usr/bin/env python3
"""
Backup torrent metadata + .torrent files before deletion.
Called by qb_public_cleanup, qb_monitor, pt_ratio_boost.

Metadata: <skill-dir>/pt_deleted_backup.json
.torrent files: <skill-dir>/torrent_backups/<hash>.torrent
"""
import json, os, re, sys, urllib.request, urllib.parse, http.cookiejar, fcntl
from datetime import datetime, timezone

_skill_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BACKUP_FILE = os.path.join(_skill_root, "pt_deleted_backup.json")
TORRENT_DIR = os.path.join(_skill_root, "torrent_backups")

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "secrets.env")
_env_cache = None

def _load_env_file():
    global _env_cache
    if _env_cache is not None:
        return
    _env_cache = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                _env_cache[k.strip()] = v.strip()

def _env(key, default=""):
    val = os.environ.get(key, "")
    if not val:
        _load_env_file()
        val = _env_cache.get(key, default)
    return val

def _qb_auth():
    """Create an authenticated qB opener."""
    qb_url = _env("QBITTORRENT_URL").rstrip("/")
    qb_user = _env("QBITTORRENT_USER")
    qb_pass = _env("QBITTORRENT_PASS")
    if not all([qb_url, qb_user, qb_pass]):
        return None, None
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", "Hermes/1.0")]
    login_data = urllib.parse.urlencode({"username": qb_user, "password": qb_pass}).encode()
    opener.open(f"{qb_url}/api/v2/auth/login", login_data, timeout=10)
    return opener, qb_url

def _download_torrent(opener, qb_url, info_hash):
    """Download .torrent file from qB via API."""
    if not re.match(r'^[a-fA-F0-9]{40}$', str(info_hash)):
        print(f"  ⚠ Invalid hash format: {info_hash[:8]}", file=sys.stderr)
        return None
    try:
        url = f"{qb_url}/api/v2/torrents/export?hash={info_hash}"
        with opener.open(url, timeout=15) as resp:
            data = resp.read()
        if data[:1] == b'd':  # bencode starts with 'd'
            os.makedirs(TORRENT_DIR, exist_ok=True)
            path = os.path.join(TORRENT_DIR, f"{info_hash}.torrent")
            with open(path, "wb") as f:
                f.write(data)
            return path
    except Exception as e:
        print(f"  ⚠ Failed to backup .torrent for {info_hash[:8]}: {e}", file=sys.stderr)
    return None

def load():
    if not os.path.exists(BACKUP_FILE):
        return []
    with open(BACKUP_FILE) as f:
        return json.load(f)

def save(entries):
    """Thread/process-safe atomic save with file lock."""
    lock_path = BACKUP_FILE + ".lock"
    os.makedirs(os.path.dirname(BACKUP_FILE), exist_ok=True)
    with open(lock_path, "w") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            existing = load()
            now = datetime.now(timezone.utc).isoformat()
            for e in entries:
                e["deleted_at"] = now
            existing.extend(entries)
            existing = existing[-500:]
            # Atomic write: temporary file + rename
            tmp = BACKUP_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            os.replace(tmp, BACKUP_FILE)
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

def backup_from_torrents(torrents, reason=""):
    """Backup torrent metadata + .torrent files before deleting."""
    opener, qb_url = _qb_auth()
    if not opener:
        print("ERROR: Cannot authenticate with qBittorrent", file=sys.stderr)
        return []

    entries = []
    for t in torrents:
        info_hash = t.get("hash", "")
        entry = {
            "hash": info_hash,
            "name": t.get("name", ""),
            "save_path": t.get("save_path", ""),
            "category": t.get("category", ""),
            "tags": t.get("tags", ""),
            "size": t.get("size", 0),
            "added_on": t.get("added_on", 0),
            "reason": reason,
        }
        # Download .torrent file
        torrent_path = _download_torrent(opener, qb_url, info_hash)
        if torrent_path:
            entry["torrent_backup"] = torrent_path
        entries.append(entry)

    if entries:
        save(entries)
        count_with_file = sum(1 for e in entries if e.get("torrent_backup"))
        print(f"Backed up {len(entries)} torrents ({count_with_file} with .torrent) to {BACKUP_FILE}", file=sys.stderr)
    return entries

if __name__ == "__main__":
    if "--list" in sys.argv:
        data = load()
        print(json.dumps(data[-50:], ensure_ascii=False, indent=2))
    elif "--clear" in sys.argv:
        with open(BACKUP_FILE, "w") as f:
            json.dump([], f)
        print("Cleared")
    elif "--restore" in sys.argv:
        # Restore a specific hash
        import shutil
        h = sys.argv[sys.argv.index("--restore") + 1] if len(sys.argv) > 2 else None
        if not h:
            print("Usage: qb_backup.py --restore <hash>")
            sys.exit(1)
        data = load()
        for entry in data:
            if entry["hash"].upper().startswith(h.upper()):
                torrent_file = entry.get("torrent_backup", "")
                if torrent_file and os.path.exists(torrent_file):
                    print(f"Found: {entry['name'][:60]}")
                    print(f"  save_path: {entry['save_path']}")
                    print(f"  category: {entry['category']}")
                    print(f"  tags: {entry['tags']}")
                    print(f"  torrent: {torrent_file}")
                    print(f"\n  To restore: qb_add.py '{torrent_file}' --category '{entry['category']}' --path '{entry['save_path']}' --tags '{entry['tags']}'")
                else:
                    print(f"Metadata only (no .torrent): {entry['name'][:60]}")
                break
        else:
            print(f"No backup found for hash {h}")
    else:
        print("Usage: qb_backup.py --list | --clear | --restore <hash>")
