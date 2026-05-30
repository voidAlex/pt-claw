#!/usr/bin/env python3
"""Cron progress check: find new completions and dead torrents."""
import json, os, re, urllib.request, urllib.parse
from datetime import datetime, timezone
from http.cookiejar import CookieJar

_skill_dir = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(_skill_dir, "..", "secrets.env")

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
                _env_cache[key.strip()] = val.strip().strip('"').strip("'")

def _env(name, default=""):
    _load_env_file()
    return os.environ.get(name, _env_cache.get(name, default))


qb_url = _env("QBITTORRENT_URL").rstrip("/")
qb_user = _env("QBITTORRENT_USER")
qb_pass = _env("QBITTORRENT_PASS")

cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open(
    f"{qb_url}/api/v2/auth/login",
    urllib.parse.urlencode({"username": qb_user, "password": qb_pass}).encode(),
    timeout=10,
)

with opener.open(f"{qb_url}/api/v2/torrents/info", timeout=30) as r:
    torrents = json.loads(r.read())

tracker_path = os.path.join(_skill_dir, "..", "pt_completed_last.txt")
known_hashes = set()
if os.path.exists(tracker_path):
    with open(tracker_path) as f:
        for line in f:
            h = line.strip().lower()
            if h and len(h) == 40:
                known_hashes.add(h)

now = datetime.now(timezone.utc)
new_completions = []
dead_torrents = []

for t in torrents:
    h = t["hash"].lower()
    progress = t.get("progress", 0)
    entry = {
        "hash": h,
        "name": t["name"],
        "size_gb": round(t.get("size", 0) / (1024**3), 2),
        "tags": t.get("tags", ""),
    }

    if progress >= 1.0 and h not in known_hashes:
        new_completions.append(entry)

    if progress == 0 and t.get("state") == "stalledDL":
        added = datetime.fromtimestamp(t.get("added_on", 0), tz=timezone.utc)
        days = (now - added).days
        if days >= 7:
            dead_torrents.append({**entry, "days_stalled": days})

seen_names = set()
unique_completions = []
for c in new_completions:
    core = re.sub(r'^\[.+?\]\s*', '', c["name"])[:40]
    if core not in seen_names:
        seen_names.add(core)
        unique_completions.append(c)

if unique_completions:
    with open(tracker_path, "a") as f:
        for c in unique_completions:
            f.write(c["hash"] + "\n")

result = {
    "known_count": len(known_hashes),
    "total_torrents": len(torrents),
    "new_completions": unique_completions,
    "dead_torrents": dead_torrents,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
