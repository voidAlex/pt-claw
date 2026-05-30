#!/usr/bin/env python3
"""
Torrent backup & restore — snapshot management for qBittorrent.

Combines backup (metadata + .torrent files) and restore (re-add to qB) in one tool.

Usage:
    python3 qb_snapshot.py backup --hash <HASH>         # backup single torrent
    python3 qb_snapshot.py backup-batch                  # backup all torrents being deleted (from stdin JSON)
    python3 qb_snapshot.py restore --hash <HASH>         # restore a single torrent by hash
    python3 qb_snapshot.py restore-all --reason <REASON> # restore all by reason
    python3 qb_snapshot.py restore-last                  # restore most recently deleted
    python3 qb_snapshot.py list                          # list recent backups
    python3 qb_snapshot.py clear                         # clear backup records
    python3 qb_snapshot.py info --hash <HASH>            # show restore info for a hash

Metadata: <skill-dir>/pt_deleted_backup.json
.torrent files: <skill-dir>/torrent_backups/<hash>.torrent
"""
import json, os, re, sys, time, urllib.request, urllib.parse, fcntl, binascii
from datetime import datetime, timezone

_skill_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BACKUP_FILE = os.path.join(_skill_root, "pt_deleted_backup.json")
TORRENT_DIR = os.path.join(_skill_root, "torrent_backups")

from _common import _env
from _qb_session import get_session


def _qb_auth():
    try:
        return get_session()
    except RuntimeError:
        return None, None


def _download_torrent(opener, qb_url, info_hash):
    if not re.match(r'^[a-fA-F0-9]{40}$', str(info_hash)):
        print(f"  ⚠ Invalid hash format: {info_hash[:8]}", file=sys.stderr)
        return None
    try:
        url = f"{qb_url}/api/v2/torrents/export?hash={info_hash}"
        with opener.open(url, timeout=15) as resp:
            data = resp.read()
        if data[:1] == b'd':
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
            tmp = BACKUP_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            os.replace(tmp, BACKUP_FILE)
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def backup_from_torrents(torrents, reason=""):
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
        torrent_path = _download_torrent(opener, qb_url, info_hash)
        if torrent_path:
            entry["torrent_backup"] = torrent_path
        entries.append(entry)

    if entries:
        save(entries)
        count_with_file = sum(1 for e in entries if e.get("torrent_backup"))
        print(f"Backed up {len(entries)} torrents ({count_with_file} with .torrent) to {BACKUP_FILE}", file=sys.stderr)
    return entries


def _add_torrent_file(opener, qb_url, torrent_path, save_path="", category="", tags=""):
    if not os.path.exists(torrent_path):
        return {"error": f".torrent file not found: {torrent_path}"}

    with open(torrent_path, "rb") as f:
        file_bytes = f.read()

    if file_bytes[:1] != b'd':
        return {"error": f"Invalid .torrent file: {torrent_path}"}

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


def _parse_args():
    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    command = args[0]

    def get_opt(flag):
        for i, a in enumerate(args):
            if a == flag and i + 1 < len(args):
                return args[i + 1]
        return None

    def has_opt(flag):
        return flag in args

    return command, get_opt, has_opt


def main():
    command, get_opt, has_opt = _parse_args()

    if command == "list":
        data = load()
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

    if command == "clear":
        with open(BACKUP_FILE, "w") as f:
            json.dump([], f)
        print("Cleared")
        return

    if command == "info":
        h = get_opt("--hash")
        if not h:
            print("Usage: qb_snapshot.py info --hash <hash>")
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
        return

    if command == "backup":
        target_hash = get_opt("--hash")
        if not target_hash:
            print("Usage: qb_snapshot.py backup --hash <hash>")
            sys.exit(1)
        opener, qb_url = _qb_auth()
        if not opener:
            print("ERROR: Cannot authenticate with qBittorrent", file=sys.stderr)
            sys.exit(1)
        try:
            with opener.open(f"{qb_url}/api/v2/torrents/info", timeout=30) as resp:
                all_torrents = json.loads(resp.read())
        except Exception as e:
            print(f"ERROR: Failed to fetch torrents: {e}", file=sys.stderr)
            sys.exit(1)
        matching = [t for t in all_torrents if t["hash"].upper().startswith(target_hash.upper())]
        if not matching:
            print(f"No torrent found for hash '{target_hash}'")
            sys.exit(1)
        entries = backup_from_torrents(matching, reason="manual_backup")
        print(json.dumps([{"hash": e["hash"], "name": e["name"]} for e in entries], ensure_ascii=False, indent=2))
        return

    if command == "backup-batch":
        torrents = json.load(sys.stdin)
        entries = backup_from_torrents(torrents, reason="manual_delete")
        print(json.dumps({"backed_up": len(entries)}, ensure_ascii=False))
        return

    if command in ("restore", "restore-all", "restore-last"):
        opener, qb_url = _qb_auth()
        if not opener:
            print(json.dumps({"error": "QBITTORRENT_* env vars not set"}))
            sys.exit(1)
        data = load()

        if command == "restore-all":
            reason = get_opt("--reason") or ""
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

        if command == "restore-last":
            if not data:
                print("No backups found")
                return
            entry = data[-1]
            print(f"Restoring most recently deleted:")
            _restore_single(opener, qb_url, entry)
            return

        if command == "restore":
            target_hash = get_opt("--hash")
            if not target_hash:
                print("Usage: qb_snapshot.py restore --hash <hash>")
                sys.exit(1)
            found = None
            for entry in reversed(data):
                if entry["hash"].upper().startswith(target_hash.upper()):
                    found = entry
                    break
            if not found:
                print(f"No backup found for hash '{target_hash}'")
                print(f"Run 'qb_snapshot.py list' to see available backups")
                sys.exit(1)
            _restore_single(opener, qb_url, found)
            return

    print(__doc__)


if __name__ == "__main__":
    main()
