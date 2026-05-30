#!/usr/bin/env python3
"""Cron progress check — compare qB completed torrents with tracked hashes."""
import os, sys, json, urllib.request, http.cookiejar, urllib.parse
from datetime import datetime, timezone

# Load secrets
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'secrets.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                key, val = line.split('=', 1)
                os.environ[key] = val.strip().strip('"').strip("'")

qb_url = os.environ['QBITTORRENT_URL']
qb_user = os.environ['QBITTORRENT_USER']
qb_pass = os.environ['QBITTORRENT_PASS']

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
login_data = f'username={urllib.parse.quote(qb_user)}&password={urllib.parse.quote(qb_pass)}'.encode()
opener.open(f'{qb_url}/api/v2/auth/login', data=login_data)

# Get all torrents
with opener.open(f'{qb_url}/api/v2/torrents/info') as resp:
    all_torrents = json.loads(resp.read())

skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Read tracked hashes
tracked_file = os.path.join(skill_dir, 'pt_completed_last.txt')
tracked = set()
if os.path.exists(tracked_file):
    with open(tracked_file) as f:
        for line in f:
            h = line.strip().lower()
            if h:
                tracked.add(h)

# Find truly completed (100% progress) torrents
completed_100 = [t for t in all_torrents if t.get('progress', 0) >= 1.0]

# New completions
new_completions = [t for t in completed_100 if t['hash'].lower() not in tracked]

# Dead torrents: 0% progress, added > 7 days ago
now = datetime.now(timezone.utc)
dead = []
for t in all_torrents:
    if t.get('progress', 0) == 0 and t.get('added_on', 0):
        added = datetime.fromtimestamp(t['added_on'], tz=timezone.utc)
        days_stalled = (now - added).days
        if days_stalled >= 7:
            dead.append({**t, 'days_stalled': days_stalled})

# Output
result = {
    'total': len(all_torrents),
    'completed_100': len(completed_100),
    'tracked': len(tracked),
    'new_completions': [{'hash': t['hash'], 'name': t['name'], 'size': t.get('size', 0)} for t in new_completions],
    'dead': [{'hash': t['hash'], 'name': t['name'], 'days_stalled': t['days_stalled']} for t in dead]
}
print(json.dumps(result, ensure_ascii=False, indent=2))
