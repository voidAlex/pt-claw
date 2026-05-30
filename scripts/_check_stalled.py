#!/usr/bin/env python3
"""Check stalled torrent ages — quick diagnostic."""
import os, sys, urllib.request, urllib.parse, json, http.cookiejar
from datetime import datetime, timezone

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
                _env_cache[key.strip()] = val.strip()

def _env(name, default=""):
    val = os.environ.get(name, "")
    if not val:
        _load_env_file()
        val = _env_cache.get(name, default)
    return val

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.addheaders = [("User-Agent", "Hermes/1.0")]
qb = _env("QBITTORRENT_URL").rstrip("/")
if not qb:
    print("Error: QBITTORRENT_URL not configured"); sys.exit(1)
login_data = urllib.parse.urlencode({"username": _env("QBITTORRENT_USER"), "password": _env("QBITTORRENT_PASS")}).encode()
opener.open(f'{qb}/api/v2/auth/login', data=login_data, timeout=10)
resp = opener.open(f'{qb}/api/v2/torrents/info', timeout=30)
torrents = json.loads(resp.read())
now = datetime.now(timezone.utc)

for t in torrents:
    added = datetime.fromtimestamp(t['added_on'], tz=timezone.utc)
    days = (now - added).days
    pct = t['progress'] * 100
    if pct < 10 and t['state'] == 'stalledDL':
        print(f'{t["name"]} | {pct:.0f}% | {t["size"]/1e9:.1f}GB | {days}d old | tags={t["tags"]}')
