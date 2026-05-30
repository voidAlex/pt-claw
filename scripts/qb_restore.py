#!/usr/bin/env python3
"""
Restore deleted torrents from backup data + .torrent files.
Part of the delete-safety chain: backup → restore loop.

Usage:
    python3 qb_restore.py --list                    # List recent backups
    python3 qb_restore.py --restore <hash>          # Restore single torrent
    python3 qb_restore.py --restore-all --reason <reason>  # Restore all by reason
    python3 qb_restore.py --last                    # Restore most recently deleted

Backup locations:
    Metadata: <skill-dir>/pt_deleted_backup.json
    .torrent: <skill-dir>/torrent_backups/<hash>.torrent
"""
import json, os, sys, time, urllib.request, urllib.parse, http.cookiejar

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

def _qb_login():
    """Login to qBittorrent, return (opener, url)."""
    qb_url = _env("QBITTORRENT_URL").rstrip("/")
    qb_user = _env("QBITTORRENT_USER")
    qb_pass = _env("QBITTORRENT_PASS")
    if not all([qb_url, qb_user, qb_pass]):
        print(json.dumps({"error": "QBITTORRENT_* env vars not set"}))
        sys.exit(1)

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", "Hermes/1.0")]
    login_data = urllib.parse.urlencode({"username": qb_user, "password": qb_pass}).encode()
    try:
        opener.open(f"{qb_url}/api/v2/auth/login", login_data, timeout=10)
    except Exception as e:
        print(json.dumps({"error": f"Login failed: {e}"}))
        sys.exit(1)
    return opener, qb_url


def _load_backup():
    """Load backup JSON, return list."""
    if not os.path.exists(BACKUP_FILE):
        return []
    with open(BACKUP_FILE) as f:
        return json.load(f)


def _add_torrent_file(opener, qb_url, torrent_path, save_path="", category="", tags=""):
    """Upload .torrent file to qB via multipart form."""
    if not os.path.exists(torrent_path):
        return {"error": f".torrent file not found: {torrent_path}"}

    with open(torrent_path, "rb") as f:
        file_bytes = f.read()

    if file_bytes[:1] != b'd':
        return {"error": f"Invalid .torrent file: {torrent_path}"}

    import binascii
    boundary = '----QB' + binascii.hexlify(os.urandom(8)).decode()

    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="torrents"; filename="restore.torrent"\r\n'
        f'Content-Type: application/x-bittorrent\r\n\r\n'
    ).encode() + file_bytes + f'\r\n--{boundary}--\r\n'.encode()

    url = f"{qb_url}/api/v2/torrents/add"
    if save_path:
        url += f"?savepath={urllib.parse.quote(save_path)}&category={urllib.parse.quote(category)}&paused=true"
    elif category:
        url += f"?category={urllib.parse.quote(category)}&paused=true"
    else:
        url += "?paused=true"

    req = urllib.request.Request(url, data=body,
                                headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    try:
        opener.open(req, timeout=30)
    except Exception as e:
        return {"error": f"Upload failed: {e}"}

    return {"success": True, "torrent_path": torrent_path}


def _find_hash_in_qb(opener, qb_url, info_hash):
    """Find a torrent in qB by hash (case-insensitive prefix match)."""
    try:
        with opener.open(f"{qb_url}/api/v2/torrents/info", timeout=30) as resp:
            torrents = json.loads(resp.read())
    except Exception:
        return None

    for t in torrents:
        if t["hash"].upper().startswith(info_hash.upper()):
            return t
    return None


def _restore_single(opener, qb_url, entry):
    """Restore a single torrent from backup entry."""
    info_hash = entry.get("hash", "")
    name = entry.get("name", "")
    save_path = entry.get("save_path", "")
    category = entry.get("category", "")
    tags = entry.get("tags", "")
    torrent_backup = entry.get("torrent_backup", "")

    print(f"  Restoring: {name[:60]}")
    print(f"    hash: {info_hash}")
    print(f"    save_path: {save_path}")
    print(f"    category: {category}")
    print(f"    tags: {tags}")

    if torrent_backup and os.path.exists(torrent_backup):
        result = _add_torrent_file(opener, qb_url, torrent_backup,
                                  save_path=save_path, category=category)
        if "error" in result:
            print(f"    ERROR: {result['error']}")
            return False
        print(f"    Uploaded .torrent → {save_path or category or 'default'}")

        if tags:
            time.sleep(1)
            qb_hash = _find_hash_in_qb(opener, qb_url, info_hash)
            if qb_hash:
                tag_data = urllib.parse.urlencode(
                    {"hashes": qb_hash["hash"], "tags": tags}).encode()
                try:
                    opener.open(f"{qb_url}/api/v2/torrents/addTags",
                               data=tag_data, timeout=10)
                    print(f"    Tags applied: {tags}")
                except Exception as e:
                    print(f"    Tag warning: {e}")
        print(f"    OK")
        return True
    else:
        print(f"    No .torrent file — metadata only. Re-download from PT site.")
        print(f"    Search keywords: {name[:60]}")
        return False


def main():

    if "--list" in sys.argv:
        data = _load_backup()
        for entry in data[-50:]:
            has_torrent = "YES" if entry.get("torrent_backup") else "no"
            print(f"  {entry.get('deleted_at', '?')[:19]} | "
                  f"{entry.get('reason', '?'):15s} | "
                  f"{entry['hash'][:12]} | "
                  f"{has_torrent:3s} | "
                  f"{entry.get('name', '?')[:60]}")
        if not data:
            print("  (no backups)")
        return

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    opener, qb_url = _qb_login()
    data = _load_backup()

    if "--restore-all" in sys.argv:
        reason = ""
        for i, a in enumerate(sys.argv):
            if a == "--reason" and i + 1 < len(sys.argv):
                reason = sys.argv[i + 1]
        matching = [e for e in data if reason and e.get("reason", "") == reason]
        if not matching:
            print(f"No backups found with reason '{reason}'")
            return
        print(f"Restoring {len(matching)} torrents with reason '{reason}'...")
        ok = 0
        for entry in matching:
            if _restore_single(opener, qb_url, entry):
                ok += 1
            time.sleep(0.5)
        print(f"\nDone: {ok}/{len(matching)} restored")
        return

    if "--last" in sys.argv:
        if not data:
            print("No backups found")
            return
        entry = data[-1]
        print(f"Restoring most recently deleted:")
        _restore_single(opener, qb_url, entry)
        return

    if "--restore" in sys.argv:
        idx = sys.argv.index("--restore")
        if idx + 1 >= len(sys.argv):
            print("Usage: qb_restore.py --restore <hash>")
            sys.exit(1)
        target_hash = sys.argv[idx + 1]
        found = None
        for entry in reversed(data):
            if entry["hash"].upper().startswith(target_hash.upper()):
                found = entry
                break
        if not found:
            print(f"No backup found for hash '{target_hash}'")
            print(f"Run --list to see available backups")
            sys.exit(1)
        _restore_single(opener, qb_url, found)
        return

    print("Usage: qb_restore.py [--list | --restore <hash> | --restore-all --reason X | --last]")
    print("  --list              List recent backup entries")
    print("  --restore <hash>    Restore by hash prefix")
    print("  --restore-all       Restore all entries matching --reason")
    print("  --last              Restore most recently deleted")


if __name__ == "__main__":
    main()
