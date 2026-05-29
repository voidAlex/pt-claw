#!/usr/bin/env python3
"""
qBittorrent monitor — check completions, download status, filter by codes/tags.

Usage:
    python3 qb_monitor.py                              # completed in 24h (default)
    python3 qb_monitor.py --full                       # full status report
    python3 qb_monitor.py --codes ROYD-318,JUFE-622    # filter by codes in name
    python3 qb_monitor.py --tags sukebei,javbus         # filter by tags
    python3 qb_monitor.py --states downloading,stalledDL # filter by state
    python3 qb_monitor.py --hours 6                     # time window
    python3 qb_monitor.py --since "2026-05-28T00:00:00"
    python3 qb_monitor.py --tracker pt_completed_last.txt
    python3 qb_monitor.py --list states                  # list all states
    python3 qb_monitor.py --list tags                    # list all tags
    python3 qb_monitor.py --list categories              # list all categories
    python3 qb_monitor.py --delete --codes ROYD-318       # delete torrents matching codes (keeps files)
    python3 qb_monitor.py --delete --tags sukebei --states stalledDL  # delete with filters
    python3 qb_monitor.py --delete --codes ROYD-318 --check  # preview only, don't delete

Combine flags: --full --codes XX --states downloading
"""

import json, os, sys, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
from http.cookiejar import CookieJar

# Import backup module
_skill_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _skill_dir)
from qb_backup import backup_from_torrents

MAX_DELETE_PER_RUN = 50

def _env(key, default=""):
    val = os.environ.get(key, default)
    # Override from secrets.env if not in env
    if val == default:
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "secrets.env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if line.startswith(key + "="):
                        val = line.split("=", 1)[1].strip()
                        break
    return val

def qb_get(endpoint: str, host: str = None) -> dict:
    qb_url = host or _env("QBITTORRENT_URL")
    qb_user = _env("QBITTORRENT_USER")
    qb_pass = _env("QBITTORRENT_PASS")

    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    login_data = urllib.parse.urlencode({"username": qb_user, "password": qb_pass}).encode()
    try:
        opener.open(f"{qb_url}/api/v2/auth/login", login_data, timeout=10)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return {"error": "Login failed"}
        raise

    full_url = f"{qb_url}{endpoint}"
    try:
        with opener.open(full_url, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def _read_tracker(path: str) -> int:
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0

def _write_tracker(path: str, epoch: int):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(str(epoch))

def fmt_size(b):
    for u in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024: return f"{b:.1f}{u}"
        b /= 1024
    return f"{b:.1f}PB"

def fmt_speed(b):
    if b == 0: return "0"
    for u in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
        if b < 1024: return f"{b:.1f}{u}"
        b /= 1024
    return f"{b:.1f}TB/s"

def parse_arg(args, flag, default=None):
    for i, a in enumerate(args):
        if a == flag and i + 1 < len(args):
            return args[i + 1]
    return default

def flag_present(args, flag):
    return flag in args

def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    torrents = qb_get("/api/v2/torrents/info")
    if isinstance(torrents, dict) and "error" in torrents:
        print(json.dumps(torrents))
        sys.exit(1)

    now = datetime.now(timezone.utc)

    # --- List modes (info only, no torrent filtering) ---
    if flag_present(args, "--list"):
        list_what = parse_arg(args, "--list", "states")
        if list_what == "states":
            states = Counter(t['state'] for t in torrents)
            for s, c in states.most_common():
                print(f"  {s}: {c}")
        elif list_what == "tags":
            tags = Counter()
            for t in torrents:
                for tag in t.get('tags', '').split(','):
                    tag = tag.strip()
                    if tag: tags[tag] += 1
            for tag, c in tags.most_common():
                print(f"  {tag}: {c}")
        elif list_what == "categories":
            cats = qb_get("/api/v2/torrents/categories")
            if isinstance(cats, dict) and "error" not in cats:
                for name, info in cats.items():
                    print(f"  {name}: {info.get('savePath', '?')}")
            else:
                cats = Counter(t.get('category', '') for t in torrents)
                for cat, c in cats.most_common():
                    print(f"  {cat or '(none)'}: {c}")
        sys.exit(0)

    # --- Filter torrents ---
    codes_filter = parse_arg(args, "--codes")
    tags_filter = parse_arg(args, "--tags")
    states_filter = parse_arg(args, "--states")

    if codes_filter:
        codes = [c.strip().upper() for c in codes_filter.split(",")]
        torrents = [t for t in torrents if any(c in t['name'].upper() for c in codes)]

    if tags_filter:
        wanted_tags = set(t.strip() for t in tags_filter.split(","))
        torrents = [t for t in torrents if wanted_tags & set(t.get('tags','').split(','))]

    if states_filter:
        wanted_states = set(s.strip() for s in states_filter.split(","))
        torrents = [t for t in torrents if t['state'] in wanted_states]

    # --- Delete mode ---
    if flag_present(args, "--delete"):
        if not torrents:
            print(json.dumps({"deleted": 0, "message": "No matching torrents"}))
            sys.exit(0)

        if len(torrents) > MAX_DELETE_PER_RUN:
            print(json.dumps({
                "error": f"SAFEGUARD: {len(torrents)} torrents match, exceeds max {MAX_DELETE_PER_RUN}",
                "total_matching": len(torrents),
                "max_allowed": MAX_DELETE_PER_RUN,
                "message": f"匹配 {len(torrents)} 个种子超过上限 {MAX_DELETE_PER_RUN}，请缩小过滤范围后重试。",
            }, ensure_ascii=False, indent=2))
            sys.exit(1)

        names = [t['name'][:80] for t in torrents]
        hashes = [t['hash'] for t in torrents]

        # --check: preview only, don't delete
        if flag_present(args, "--check"):
            print(json.dumps({
                "check_mode": True,
                "would_delete": len(hashes),
                "would_delete_list": [{
                    "hash": t["hash"][:12],
                    "name": t["name"][:80],
                    "size": fmt_size(t["size"]),
                    "state": t["state"],
                    "tags": t.get("tags", ""),
                } for t in torrents],
                "tip": "确认删除请运行: python3 qb_monitor.py --delete [same filters]",
            }, ensure_ascii=False, indent=2))
            sys.exit(0)
        
        # Backup before delete
        backup_from_torrents(torrents, reason="manual_delete")
        
        # Delete without removing files (POST only, GET not supported)
        cj = CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        qb_url = _env("QBITTORRENT_URL")
        qb_user = _env("QBITTORRENT_USER")
        qb_pass = _env("QBITTORRENT_PASS")
        login_d = urllib.parse.urlencode({"username": qb_user, "password": qb_pass}).encode()
        opener.open(f"{qb_url}/api/v2/auth/login", login_d, timeout=10)
        data = urllib.parse.urlencode({"hashes": "|".join(hashes), "deleteFiles": "false"}).encode()
        req = urllib.request.Request(f"{qb_url}/api/v2/torrents/delete", data=data)
        with opener.open(req, timeout=10) as resp:
            pass
        print(json.dumps({"deleted": len(hashes), "names": names}, ensure_ascii=False))
        sys.exit(0)

    # --- Full status mode ---
    if flag_present(args, "--full"):
        by_state = defaultdict(list)
        for t in torrents:
            by_state[t['state']].append(t)

        dl_speed = sum(t['dlspeed'] for t in torrents)
        ul_speed = sum(t['upspeed'] for t in torrents)

        result = {
            "total": len(torrents),
            "dl_speed": fmt_speed(dl_speed),
            "ul_speed": fmt_speed(ul_speed),
            "time": now.isoformat(),
            "states": {k: len(v) for k, v in by_state.items()},
            "downloading": [],
            "completed_recent": [],
            "dead": [],
        }

        downloading = by_state.get('downloading', []) + by_state.get('forcedDL', []) + by_state.get('stalledDL', [])
        for t in sorted(downloading, key=lambda x: -x['progress']):
            result["downloading"].append({
                "name": t['name'],
                "progress": round(t['progress'] * 100),
                "size": fmt_size(t['size']),
                "dlspeed": fmt_speed(t['dlspeed']),
                "tags": t.get('tags', ''),
                "state": t['state'],
            })

        # Dead: 0% > 7 days
        for t in torrents:
            if t['progress'] == 0 and t['state'] in ('stalledDL',) and now.timestamp() - t['added_on'] > 7*86400:
                result["dead"].append({"name": t['name'], "added_days": int((now.timestamp() - t['added_on']) / 86400)})

        # Completed in 7 days
        for t in torrents:
            if t['progress'] == 1.0 and t.get('completion_on', 0) > 0:
                if now.timestamp() - t['completion_on'] < 7*86400:
                    result["completed_recent"].append({
                        "name": t['name'],
                        "size": fmt_size(t['total_size']),
                        "completed_hours_ago": round((now.timestamp() - t['completion_on']) / 3600, 1),
                        "tags": t.get('tags', ''),
                    })

        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    # --- Default: completed torrents in time window ---
    tracker_path = parse_arg(args, "--tracker")

    if "--since" in args:
        idx = args.index("--since")
        cutoff = datetime.fromisoformat(args[idx + 1])
    elif tracker_path:
        last_epoch = _read_tracker(tracker_path)
        cutoff = datetime.fromtimestamp(last_epoch, tz=timezone.utc)
    else:
        hours = int(parse_arg(args, "--hours", "24"))
        cutoff = now - timedelta(hours=hours)

    completed = []
    max_completion_epoch = 0

    for t in torrents:
        if t.get("state") not in ("pausedUP", "uploading", "forcedUP", "stalledUP", "checkingUP"):
            continue
        completion_time = t.get("completion_on", 0)
        if completion_time == 0:
            continue
        completion_dt = datetime.fromtimestamp(completion_time, tz=timezone.utc)
        if completion_dt < cutoff:
            continue
        max_completion_epoch = max(max_completion_epoch, completion_time)
        completed.append({
            "name": t.get("name", ""),
            "size": fmt_size(t.get("size", 0)),
            "size_bytes": t.get("size", 0),
            "category": t.get("category", ""),
            "completed_at": completion_dt.isoformat(),
            "ratio": round(t.get("ratio", 0), 2),
            "save_path": t.get("save_path", ""),
            "state": t.get("state"),
            "tags": t.get("tags", ""),
        })

    if tracker_path and max_completion_epoch > 0:
        _write_tracker(tracker_path, max_completion_epoch)

    print(json.dumps({
        "cutoff": cutoff.isoformat(),
        "count": len(completed),
        "completed": completed,
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
