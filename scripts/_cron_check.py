#!/usr/bin/env python3
"""Cron progress check: new completions, dead torrents, public auto-cleanup."""
import json, os, re, sys, fcntl, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from http.cookiejar import CookieJar

_skill_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _skill_dir)
from qb_backup import backup_from_torrents

_skill_root = os.path.join(_skill_dir, "..")
ENV_FILE = os.path.join(_skill_root, "secrets.env")

PUBLIC_TAGS = {"sukebei", "javbus"}
MAX_DELETE_PER_RUN = 50
MAX_PUBLIC_RATIO = 0.20
COMPLETED_STATES = {"pausedUP", "uploading", "forcedUP", "stalledUP"}

STATE_FILE = os.path.join(_skill_root, "pt_notify_state.json")
TRACKER_FILE = os.path.join(_skill_root, "pt_completed_last.txt")

_env_cache = None


def _load_env_file():
    global _env_cache
    if _env_cache is not None:
        return
    _env_cache = {}
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                _env_cache[key.strip()] = val.strip()


def _env(name, default=""):
    val = os.environ.get(name, "")
    if not val:
        _load_env_file()
        val = _env_cache.get(name, default)
    return val


def _default_state():
    return {
        "dead_torrents": {},
        "notify_config": {
            "dead_interval_hours": 6,
            "dead_max_reminders": 20,
        }
    }


def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
            if "dead_torrents" not in data:
                data["dead_torrents"] = {}
            if "notify_config" not in data:
                data["notify_config"] = _default_state()["notify_config"]
            normalized = {}
            for k, v in data["dead_torrents"].items():
                normalized[k.lower()] = v
            data["dead_torrents"] = normalized
            return data
        except (json.JSONDecodeError, IOError):
            pass
    return _default_state()


def _save_state(state):
    tmp = STATE_FILE + ".tmp"
    lock_path = STATE_FILE + ".lock"
    with open(lock_path, "w") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            with open(tmp, "w") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, STATE_FILE)
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


qb_url = _env("QBITTORRENT_URL").rstrip("/")
qb_user = _env("QBITTORRENT_USER")
qb_pass = _env("QBITTORRENT_PASS")
if not qb_url:
    print(json.dumps({"error": "QBITTORRENT_URL not configured"}))
    sys.exit(1)

cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def _request(url, data=None, timeout=30):
    req = urllib.request.Request(url, data=data)
    req.add_header("User-Agent", "Hermes/1.0")
    return opener.open(req, timeout=timeout)


_request(
    f"{qb_url}/api/v2/auth/login",
    urllib.parse.urlencode({"username": qb_user, "password": qb_pass}).encode(),
    timeout=10,
)

with _request(f"{qb_url}/api/v2/torrents/info", timeout=30) as r:
    torrents = json.loads(r.read())

known_hashes = set()
if os.path.exists(TRACKER_FILE):
    with open(TRACKER_FILE) as f:
        for line in f:
            h = line.strip().lower()
            if h and len(h) == 40:
                known_hashes.add(h)

state = _load_state()
now = datetime.now(timezone.utc)
dry_run = _env("QB_CLEANUP_DRY_RUN") == "1"

new_completions = []
dead_all = []
dead_to_notify = []
completed_public = []

for t in torrents:
    h = t["hash"].lower()
    progress = t.get("progress", 0)
    tstate = t.get("state", "")
    tags_str = t.get("tags", "")
    tags_set = set(tag.strip() for tag in tags_str.split(",") if tag.strip())
    size = t.get("size", 0)
    added_on = t.get("added_on", 0)
    size_gb = round(size / (1024**3), 2)

    entry = {
        "hash": h,
        "name": t["name"],
        "size_gb": size_gb,
        "tags": tags_str,
    }

    if progress >= 1.0 and h not in known_hashes:
        new_completions.append(entry)

    if tags_set & PUBLIC_TAGS:
        if tstate in COMPLETED_STATES or progress >= 1.0:
            completed_public.append(t)

    if progress == 0 and tstate == "stalledDL" and added_on > 0:
        added_dt = datetime.fromtimestamp(added_on, tz=timezone.utc)
        days = (now - added_dt).days
        if days >= 7:
            dead_all.append(h)
            dead_entry = {**entry, "days_stalled": days}

            if h in state["dead_torrents"]:
                rec = state["dead_torrents"][h]
                last_notified = datetime.fromisoformat(rec["last_notified"]).replace(tzinfo=timezone.utc)
                interval = timedelta(hours=state["notify_config"]["dead_interval_hours"])
                max_reminders = state["notify_config"].get("dead_max_reminders", 20)

                if rec["notify_count"] < max_reminders and now >= last_notified + interval:
                    dead_to_notify.append({**dead_entry, "remind_count": rec["notify_count"] + 1})
                    rec["last_notified"] = now.strftime("%Y-%m-%dT%H:%M:%S")
                    rec["notify_count"] += 1
                    rec["days_stalled"] = days
                    rec["name"] = t["name"]
                    rec["tags"] = tags_str
                    rec["size_gb"] = size_gb
            else:
                state["dead_torrents"][h] = {
                    "name": t["name"],
                    "tags": tags_str,
                    "size_gb": size_gb,
                    "days_stalled": days,
                    "first_seen": now.strftime("%Y-%m-%dT%H:%M:%S"),
                    "last_notified": now.strftime("%Y-%m-%dT%H:%M:%S"),
                    "notify_count": 1,
                }
                dead_to_notify.append({**dead_entry, "remind_count": 1})

to_remove = [h for h in state["dead_torrents"] if h not in dead_all]
for h in to_remove:
    del state["dead_torrents"][h]

silenced_dead = len(dead_all) - len(dead_to_notify)

seen_names = set()
unique_completions = []
for c in new_completions:
    core = re.sub(r'^\[.+?\]\s*', '', c["name"])[:40]
    if core not in seen_names:
        seen_names.add(core)
        unique_completions.append(c)

if unique_completions:
    with open(TRACKER_FILE, "a") as f:
        for c in unique_completions:
            f.write(c["hash"] + "\n")

auto_cleaned = []
if completed_public:
    total_count = len(torrents)
    public_count = sum(
        1 for t in torrents
        if set(tag.strip() for tag in t.get("tags", "").split(",") if tag.strip()) & PUBLIC_TAGS
    )

    if total_count > 0 and public_count / total_count > MAX_PUBLIC_RATIO:
        pass
    else:
        to_delete = completed_public[:MAX_DELETE_PER_RUN]

        if not dry_run:
            backup_from_torrents(to_delete, reason="cron_public_cleanup")
            for t in to_delete:
                try:
                    data = urllib.parse.urlencode(
                        {"hashes": t["hash"], "deleteFiles": "false"}
                    ).encode()
                    _request(f"{qb_url}/api/v2/torrents/delete", data=data, timeout=10)
                    auto_cleaned.append({
                        "name": t["name"],
                        "size_gb": round(t.get("size", 0) / (1024**3), 2),
                        "tags": t.get("tags", ""),
                        "hash": t["hash"].lower(),
                    })
                except Exception:
                    pass
        else:
            for t in to_delete:
                auto_cleaned.append({
                    "name": t["name"],
                    "size_gb": round(t.get("size", 0) / (1024**3), 2),
                    "tags": t.get("tags", ""),
                    "hash": t["hash"].lower(),
                })

_save_state(state)

downloading = sum(1 for t in torrents if 0 < t.get("progress", 0) < 1.0)
seeding = sum(1 for t in torrents if t.get("progress", 0) >= 1.0)

notifications = []

if unique_completions:
    notifications.append({
        "type": "completion",
        "icon": "✅",
        "items": unique_completions,
    })

if dead_to_notify:
    notifications.append({
        "type": "dead_reminder",
        "icon": "💀",
        "summary": f"{len(dead_to_notify)} 个死种待处理",
        "items": [
            {
                "name": d["name"],
                "size_gb": d["size_gb"],
                "tags": d["tags"],
                "days_stalled": d["days_stalled"],
                "remind_count": d["remind_count"],
                "hash": d["hash"],
            }
            for d in dead_to_notify
        ],
        "action_hint": "回复「删」清理死种",
    })

if auto_cleaned:
    notifications.append({
        "type": "auto_cleaned",
        "icon": "🧹",
        "items": auto_cleaned,
        "note": "已完成公开磁链已自动清理（文件保留，种子移除）",
    })

has_content = bool(unique_completions or dead_to_notify or auto_cleaned)

if not has_content:
    print(json.dumps({"silent": True}, ensure_ascii=False))
else:
    result = {
        "notifications": notifications,
        "silenced": {"dead": silenced_dead},
        "stats": {
            "total": len(torrents),
            "downloading": downloading,
            "seeding": seeding,
            "dead": len(dead_all),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
