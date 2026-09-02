#!/usr/bin/env python3
"""Cron progress check: new completions, dead torrents, public auto-cleanup."""
import json, os, re, sys, fcntl, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

from _common import _env, PUBLIC_TAGS, MAX_DELETE_PER_RUN, MAX_PUBLIC_RATIO, COMPLETED_STATES
from _logger import get_logger
from _qb_session import get_session

log = get_logger("_cron_check")

_skill_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _skill_dir)
from qb_snapshot import backup_from_torrents

from download_history import cmd_complete_by_hash

_skill_root = os.path.join(_skill_dir, "..")

STATE_FILE = os.path.join(_skill_root, "pt_notify_state.json")
TRACKER_FILE = os.path.join(_skill_root, "pt_completed_last.txt")
JF_REFRESH_STATE_FILE = os.path.join(_skill_root, "pt_jf_refresh_state.json")

JF_REFRESH_MIN_INTERVAL_MINUTES = 30
JF_REFRESH_SKIP_PATHS = "/downloads"


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
            with open(STATE_FILE, encoding="utf-8") as f:
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
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, STATE_FILE)
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    try:
        os.unlink(lock_path)
    except OSError:
        pass


def _load_jf_refresh_state():
    """Return last refresh time from pt_jf_refresh_state.json, or None (missing/corrupt)."""
    try:
        with open(JF_REFRESH_STATE_FILE, encoding="utf-8") as f:
            last = datetime.fromisoformat(json.load(f)["last_refresh"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return last


def _save_jf_refresh_state(dt):
    try:
        tmp = JF_REFRESH_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"last_refresh": dt.isoformat()}, f)
        os.replace(tmp, JF_REFRESH_STATE_FILE)
    except OSError as e:
        log.warning("failed to write %s: %s", JF_REFRESH_STATE_FILE, e)
        return False
    return True


def _jellyfin_refresh(now, completions):
    """POST /Library/Refresh on every Jellyfin instance for new completions.

    Completions under JF_REFRESH_SKIP_PATHS prefixes (default /downloads)
    or with public tags are excluded; all instances share a single rate
    limit (JF_REFRESH_MIN_INTERVAL_MINUTES, default 30) recorded in
    pt_jf_refresh_state.json. Failures only log a warning and never affect
    the notification flow. Returns the jf_refresh output dict.
    """
    result = {"triggered": False, "skipped": None, "servers": []}
    # Master switch: only "0" disables; unset or any other value stays enabled.
    if _env("JF_REFRESH_ENABLED") == "0":
        return {"triggered": False, "skipped": "disabled", "servers": []}
    skip_raw = _env("JF_REFRESH_SKIP_PATHS") or JF_REFRESH_SKIP_PATHS
    skip_paths = [p.strip() for p in skip_raw.split(",") if p.strip()]
    candidates = [
        c for c in completions
        if not (set(tag.strip() for tag in c.get("tags", "").split(",") if tag.strip()) & PUBLIC_TAGS)
        and not any(p.lower() in c.get("save_path", "").lower() for p in skip_paths)
    ]
    excluded = len(completions) - len(candidates)
    if excluded:
        log.info("jf refresh excluded %d/%d completions (downloads path or public tags)", excluded, len(completions))
    if not candidates:
        result["skipped"] = "filtered"
        return result

    try:
        interval = timedelta(minutes=int(_env("JF_REFRESH_MIN_INTERVAL_MINUTES") or JF_REFRESH_MIN_INTERVAL_MINUTES))
    except ValueError:
        log.warning("jf refresh invalid JF_REFRESH_MIN_INTERVAL_MINUTES, using default %d", JF_REFRESH_MIN_INTERVAL_MINUTES)
        interval = timedelta(minutes=JF_REFRESH_MIN_INTERVAL_MINUTES)
    last = _load_jf_refresh_state()
    if last is not None and now - last < interval:
        result["skipped"] = "rate_limited"
        result["last_refresh"] = last.isoformat()
        log.info("jf refresh rate-limited, last refresh at %s", last.isoformat())
        return result

    instances = []
    n = 1
    while True:
        url = _env(f"JELLYFIN{n}_URL")
        if not url:
            break
        key = _env(f"JELLYFIN{n}_API_KEY")
        if key:
            instances.append((n, url.rstrip("/"), key))
        else:
            log.warning("jf refresh: JELLYFIN%d URL set but no API key, skipped", n)
        n += 1
    if not instances:
        result["skipped"] = "no_servers"
        log.warning("jf refresh: no JELLYFIN{N}_URL/_API_KEY configured")
        return result

    # JF instances are intranet (10.10.1.x): direct connection, never via PT_PROXY
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    ok = 0
    for n, url, key in instances:
        name = f"JELLYFIN{n}"
        try:
            req = urllib.request.Request(
                f"{url}/Library/Refresh?api_key={urllib.parse.quote(key, safe='')}",
                data=b"",
                method="POST",
            )
            with opener.open(req, timeout=10) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code
        except (urllib.error.URLError, OSError) as e:
            status = f"error: {e}"
        result["servers"].append({"server": name, "status": status})
        if isinstance(status, int) and 200 <= status < 300:
            ok += 1
            log.info("jf refresh ok %s status=%s", name, status)
        else:
            log.warning("jf refresh failed %s status=%s", name, status)

    result["triggered"] = True
    # window is consumed once a round was attempted (>=1 instance), even if all failed
    if _save_jf_refresh_state(now):
        result["last_refresh"] = now.isoformat()
    log.info("jf refresh triggered completions=%d ok=%d total=%d", len(candidates), ok, len(instances))
    return result


def main():
    log.info("cron check started")
    try:
        opener, qb_url = get_session()
    except RuntimeError as e:
        log.error("qb session failed: %s", e)
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    try:
        with opener.open(f"{qb_url}/api/v2/torrents/info", timeout=30) as r:
            torrents = json.loads(r.read())
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        log.error("failed to fetch torrents from qB: %s", e)
        print(json.dumps({"error": f"qBittorrent connection failed: {e}"}))
        sys.exit(1)
    log.info("fetched %d torrents from qBittorrent", len(torrents))

    known_hashes = set()
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, encoding="utf-8") as f:
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
    jf_refresh = None

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
            "save_path": t.get("save_path", ""),
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
    if to_remove:
        log.info("cleaned up %d resolved dead torrent entries", len(to_remove))

    silenced_dead = len(dead_all) - len(dead_to_notify)
    if dead_all:
        log.warning("dead torrents total=%d notifying=%d silenced=%d", len(dead_all), len(dead_to_notify), silenced_dead)

    seen_names = set()
    unique_completions = []
    for c in new_completions:
        core = re.sub(r'^\[.+?\]\s*', '', c["name"])[:40]
        if core not in seen_names:
            seen_names.add(core)
            unique_completions.append(c)

    if unique_completions:
        log.info("new completions count=%d", len(unique_completions))
        with open(TRACKER_FILE, "a", encoding="utf-8") as f:
            for c in unique_completions:
                f.write(c["hash"] + "\n")

        for c in unique_completions:
            try:
                cmd_complete_by_hash(c["hash"], c["name"])
            except Exception as e:
                log.error("complete_by_hash failed hash=%s error=%s", c["hash"][:12], e)
    jf_refresh = _jellyfin_refresh(now, unique_completions)

    auto_cleaned = []
    if completed_public:
        log.info("public cleanup candidates count=%d", len(completed_public))
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
                backed_up = backup_from_torrents(to_delete, reason="cron_public_cleanup")
                if not backed_up and to_delete:
                    print("WARNING: Backup failed, skipping deletion to prevent data loss", file=sys.stderr)
                else:
                    for t in to_delete:
                        try:
                            data = urllib.parse.urlencode(
                                {"hashes": t["hash"], "deleteFiles": "false"}
                            ).encode()
                            req = urllib.request.Request(f"{qb_url}/api/v2/torrents/delete", data=data)
                            opener.open(req, timeout=10)
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
        log.info("completion notification count=%d", len(unique_completions))
        notifications.append({
            "type": "completion",
            "icon": "✅",
            "items": unique_completions,
        })

    if dead_to_notify:
        log.warning("dead torrent notification count=%d", len(dead_to_notify))
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
        log.info("auto cleaned public torrents count=%d", len(auto_cleaned))
        notifications.append({
            "type": "auto_cleaned",
            "icon": "🧹",
            "items": auto_cleaned,
            "note": "已完成公开磁链已自动清理（文件保留，种子移除）",
        })

    has_content = bool(unique_completions or dead_to_notify or auto_cleaned)

    if not has_content:
        log.info("cron check silent — no notifications")
        print(json.dumps({"silent": True}, ensure_ascii=False))
    else:
        result = {
            "notifications": notifications,
            "silenced": {"dead": silenced_dead},
            "jf_refresh": jf_refresh,
            "stats": {
                "total": len(torrents),
                "downloading": downloading,
                "seeding": seeding,
                "dead": len(dead_all),
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    log.info("cron check finished total=%d downloading=%d seeding=%d", len(torrents), downloading, seeding)


if __name__ == "__main__":
    main()
