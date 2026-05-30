#!/usr/bin/env python3
"""
Check qBittorrent for public magnet torrents (sukebei/javbus tags ONLY).
1. Completed → delete torrent, keep files
2. Dead (>7 days at 0% progress) → report

CRITICAL: Public detection is TAG-ONLY (sukebei/javbus).
Tracker URL matching is DANGEROUS — PT seeds also include public trackers.

SAFEGUARDS (防误删三道防线):
1. MAX_DELETE_PER_RUN = 50 — 单次最多删50个，超限中止
2. MAX_PUBLIC_RATIO = 0.20 — 如果"公开种"占总种子超20%，判定异常中止
3. DRY_RUN — 设置环境变量 QB_CLEANUP_DRY_RUN=1 只报告不执行
"""
import json, os, sys, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar

# Import backup module
_skill_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _skill_dir)
from qb_backup import backup_from_torrents

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
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    _env_cache[k.strip()] = v.strip()


def _env(key, default=""):
    val = os.environ.get(key, "")
    if not val:
        _load_env_file()
        val = _env_cache.get(key, default)
    return val


PUBLIC_TAGS = {"sukebei", "javbus"}
MAX_DELETE_PER_RUN = 50
MAX_PUBLIC_RATIO = 0.20
DRY_RUN = _env("QB_CLEANUP_DRY_RUN") == "1"
CHECK_MODE = "--check" in sys.argv


def main():
    _check = CHECK_MODE or DRY_RUN

    qb_url = _env("QBITTORRENT_URL").rstrip("/")
    qb_user = _env("QBITTORRENT_USER")
    qb_pass = _env("QBITTORRENT_PASS")

    if not all([qb_url, qb_user, qb_pass]):
        print(json.dumps({"error": "Missing QBITTORRENT_* env vars"}))
        sys.exit(1)

    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", "Hermes/1.0")]
    try:
        opener.open(f"{qb_url}/api/v2/auth/login",
            data=urllib.parse.urlencode({"username": qb_user, "password": qb_pass}).encode(),
            timeout=10)
    except Exception as e:
        print(json.dumps({"error": f"Login failed: {e}"}))
        sys.exit(1)

    try:
        with opener.open(f"{qb_url}/api/v2/torrents/info", timeout=60) as resp:
            all_torrents = json.loads(resp.read())
    except Exception as e:
        print(json.dumps({"error": f"Get torrents failed: {e}"}))
        sys.exit(1)

    total_count = len(all_torrents)
    now = datetime.now(timezone.utc)

    # TAG-ONLY detection
    public_torrents = []
    for t in all_torrents:
        torrent_tags = set(tag.strip() for tag in t.get("tags", "").split(",") if tag.strip())
        if torrent_tags & PUBLIC_TAGS:
            public_torrents.append(t)

    public_count = len(public_torrents)

    # ---- SAFEGUARD 1: Public ratio check ----
    if total_count > 0 and public_count / total_count > MAX_PUBLIC_RATIO:
        print(json.dumps({
            "error": "SAFEGUARD: public ratio too high — possible misclassification",
            "total_torrents": total_count,
            "public_count": public_count,
            "public_ratio": round(public_count / total_count, 3),
            "max_allowed_ratio": MAX_PUBLIC_RATIO,
            "message": f"公开种占比 {public_count}/{total_count} = {public_count/total_count:.1%}，超过 {MAX_PUBLIC_RATIO:.0%} 安全阈值，中止删除。请人工检查。",
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    completed_to_delete = []
    dead_to_report = []

    for t in public_torrents:
        name = t.get("name", "?")
        progress = t.get("progress", 0)
        state = t.get("state", "")
        added_on = t.get("added_on", 0)
        size = t.get("size", 0)
        tags = t.get("tags", "")
        h = t.get("hash", "")
        save_path = t.get("save_path", "")
        category = t.get("category", "")

        size_str = f"{size / (1024**3):.1f}GB" if size else "?"

        if state in ("pausedUP", "uploading", "forcedUP", "stalledUP") or progress >= 1.0:
            completed_to_delete.append(t)
        elif progress == 0 and state in ("pausedDL", "stalledDL", "queuedDL", "downloading", "forcedDL") and added_on > 0 and (now.timestamp() - added_on) >= 7 * 24 * 3600:
            age_days = round((now.timestamp() - added_on) / 86400, 1)
            dead_to_report.append(t)

    # ---- SAFEGUARD 2: Max delete cap ----
    if len(completed_to_delete) > MAX_DELETE_PER_RUN:
        if _check:
            # Check mode: show capped list
            to_delete_now = completed_to_delete[:MAX_DELETE_PER_RUN]
            print(json.dumps({
                "check_mode": True,
                "total_torrents": total_count,
                "public_count": public_count,
                "cap_exceeded": True,
                "total_would_delete": len(completed_to_delete),
                "max_per_run": MAX_DELETE_PER_RUN,
                "would_delete": len(to_delete_now),
                "would_delete_list": [{
                    "hash": t["hash"][:12],
                    "name": t["name"][:80],
                    "size": f"{t.get('size', 0) / (1024**3):.1f}GB" if t.get("size") else "?",
                    "state": t["state"],
                    "tags": t.get("tags", ""),
                } for t in to_delete_now],
                "skipped_count": len(completed_to_delete) - MAX_DELETE_PER_RUN,
                "dead": [{
                    "hash": d["hash"][:12],
                    "name": d["name"][:80],
                    "size": f"{d.get('size', 0) / (1024**3):.1f}GB" if d.get("size") else "?",
                    "age_days": round((now.timestamp() - d.get("added_on", 0)) / 86400, 1),
                    "tags": d.get("tags", ""),
                } for d in dead_to_report],
                "tip": f"待删{len(completed_to_delete)}个超上限{MAX_DELETE_PER_RUN}，仅删前{MAX_DELETE_PER_RUN}个。确认请运行: python3 qb_public_cleanup.py",
            }, ensure_ascii=False, indent=2))
            return
        print(json.dumps({
            "error": "SAFEGUARD: delete cap exceeded",
            "to_delete": len(completed_to_delete),
            "max_allowed": MAX_DELETE_PER_RUN,
            "message": f"待删 {len(completed_to_delete)} 个超过上限 {MAX_DELETE_PER_RUN}，中止。请人工确认后分批删除。",
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    else:
        to_delete_now = completed_to_delete

    # ---- SAFEGUARD 3: dry-run / check mode ----
    if _check:
        # --check mode: show what would be deleted, don't act
        print(json.dumps({
            "check_mode": True,
            "total_torrents": total_count,
            "public_count": public_count,
            "would_delete": len(to_delete_now),
            "would_delete_list": [{
                "hash": t["hash"][:12],
                "name": t["name"][:80],
                "size": f"{t.get('size', 0) / (1024**3):.1f}GB" if t.get("size") else "?",
                "state": t["state"],
                "tags": t.get("tags", ""),
            } for t in to_delete_now],
            "dead": [{
                "hash": d["hash"][:12],
                "name": d["name"][:80],
                "size": f"{d.get('size', 0) / (1024**3):.1f}GB" if d.get("size") else "?",
                "age_days": round((now.timestamp() - d.get("added_on", 0)) / 86400, 1),
                "tags": d.get("tags", ""),
            } for d in dead_to_report],
            "tip": "确认删除请运行: python3 qb_public_cleanup.py",
        }, ensure_ascii=False, indent=2))
        return

    # ---- Backup before delete ----
    if to_delete_now:
        backup_from_torrents(to_delete_now, reason="public_cleanup")

    # Delete (keep files)
    deleted = []
    failed = []
    for t in to_delete_now:
        h = t["hash"]
        try:
            data = urllib.parse.urlencode({"hashes": h, "deleteFiles": "false"}).encode()
            opener.open(f"{qb_url}/api/v2/torrents/delete", data=data, timeout=10)
            deleted.append({
                "hash": h[:12],
                "name": t["name"][:80],
                "size": f"{t.get('size', 0) / (1024**3):.1f}GB" if t.get("size") else "?",
                "tags": t.get("tags", ""),
            })
        except Exception as e:
            failed.append({"hash": h[:12], "name": t["name"][:80], "error": str(e)})

    result = {
        "total_torrents": total_count,
        "public_count": public_count,
        "deleted": deleted,
        "dead": [{
            "hash": d["hash"][:12],
            "name": d["name"][:80],
            "size": f"{d.get('size', 0) / (1024**3):.1f}GB" if d.get("size") else "?",
            "age_days": round((now.timestamp() - d.get("added_on", 0)) / 86400, 1),
            "tags": d.get("tags", ""),
        } for d in dead_to_report],
    }
    if failed:
        result["failed"] = failed

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
