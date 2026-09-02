#!/usr/bin/env python3
"""Batch JF ownership check — cron-safe (no pipes), for chase dedup.

Usage:
    python3 scripts/jf_batch_check.py <codes_file> [outdir]

- codes_file: one code per line (e.g. /tmp/jbcheck/YYYYMMDD/not_downloaded.txt)
- outdir: default = dirname(codes_file); writes jf_found.txt / jf_notfound.txt

Reads JELLYFIN1_URL / JELLYFIN1_API_KEY / JELLYFIN2_URL / JELLYFIN2_API_KEY
from secrets.env (parent of scripts/). Checks each code against JF1 first,
falls back to JF2 if JF1 returns 0 or errors — redundancy if one server is down.
No hardcoded credentials: key rotation only requires editing secrets.env.

Verified 2026-08-20: 123 codes checked in ~2s.
"""
import json, os, ssl, sys, urllib.parse, urllib.request


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    codes_file = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(codes_file))
    os.makedirs(outdir, exist_ok=True)

    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = load_env(os.path.join(skill_dir, 'secrets.env'))
    jf_pairs = []
    for i in (1, 2):
        url = env.get(f'JELLYFIN{i}_URL', '').rstrip('/')
        key = env.get(f'JELLYFIN{i}_API_KEY', '')
        if url and key:
            jf_pairs.append((url, key))
    if not jf_pairs:
        print("ERROR: no JELLYFIN config found in secrets.env")
        return 1

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    codes = [l.strip() for l in open(codes_file) if l.strip()]

    found, notfound = [], []
    for code in codes:
        in_jf = False
        for url, key in jf_pairs:
            try:
                q = urllib.parse.quote(code)
                req = urllib.request.Request(
                    f"{url}/Items?searchTerm={q}&recursive=true&limit=1",
                    headers={"X-MediaBrowser-Token": key})
                with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                    d = json.loads(resp.read())
                    if d.get("TotalRecordCount", 0) > 0:
                        in_jf = True
                        break
            except Exception:
                continue  # try next server
        (found if in_jf else notfound).append(code)

    with open(os.path.join(outdir, 'jf_found.txt'), 'w') as f:
        f.write('\n'.join(found) + ('\n' if found else ''))
    with open(os.path.join(outdir, 'jf_notfound.txt'), 'w') as f:
        f.write('\n'.join(notfound) + ('\n' if notfound else ''))
    print(f"Total: {len(codes)}, In JF: {len(found)}, Not in JF: {len(notfound)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
