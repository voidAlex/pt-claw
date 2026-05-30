#!/usr/bin/env python3
"""
Cross-seed (辅种) — verify and add matching torrents across PT sites.

Usage:
    python3 cross_seed.py verify --input results.json
    python3 cross_seed.py verify --stdin
    python3 cross_seed.py create-task --title "Movie" --items verified.json --save-path /media/downloads
    python3 cross_seed.py create-task --title "Movie" --stdin --save-path /media/downloads
    python3 cross_seed.py search "流浪地球2" --save-path /media/downloads [--site mteam]
    python3 cross_seed.py list
    python3 cross_seed.py send --task-id TASK_ID [--base-only | --others-only]
    python3 cross_seed.py delete --task-id TASK_ID
    python3 cross_seed.py batch-scan [--site mteam,pttime] [--limit 50]

Pipeline examples:
    python3 pt_search.py "流浪地球2" | python3 cross_seed.py verify --stdin
    python3 cross_seed.py verify --stdin < results.json | python3 cross_seed.py create-task --title "Movie" --stdin --save-path /media/downloads
    python3 cross_seed.py search "流浪地球2" --save-path /media/downloads
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

from _common import _env, _env_matching, _fmt_size, _load_env_file
from _proxy import using_proxy
from _search_cache import cache_get, cache_put

_skill_dir = os.path.dirname(os.path.abspath(__file__))
TASKS_FILE = os.path.join(_skill_dir, "cross_seed_tasks.json")


# ── Bencode parser ─────────────────────────────────────────────

def _bencode_decode(data: bytes, pos: int = 0) -> tuple:
    ch = data[pos:pos + 1]
    if ch == b"i":
        end = data.index(b"e", pos)
        return int(data[pos + 1:end]), end + 1
    elif ch == b"l":
        result = []
        pos += 1
        while data[pos:pos + 1] != b"e":
            item, pos = _bencode_decode(data, pos)
            result.append(item)
        return result, pos + 1
    elif ch == b"d":
        result = {}
        pos += 1
        while data[pos:pos + 1] != b"e":
            key, pos = _bencode_decode(data, pos)
            val, pos = _bencode_decode(data, pos)
            result[key] = val
        return result, pos + 1
    elif ch.isdigit():
        colon = data.index(b":", pos)
        length = int(data[pos:colon])
        start = colon + 1
        return data[start:start + length], start + length
    else:
        raise ValueError(f"Invalid bencode at pos {pos}: {ch!r}")


def _bencode_decode_with_raw(data: bytes, pos: int = 0) -> tuple:
    """Decode bencoded value, also returning its raw bytes."""
    start = pos
    ch = data[pos:pos + 1]
    if ch == b"i":
        end = data.index(b"e", pos)
        return int(data[pos + 1:end]), end + 1, data[start:end + 1]
    elif ch == b"l":
        result = []
        pos += 1
        raw_parts = [b"l"]
        while data[pos:pos + 1] != b"e":
            item, pos, raw = _bencode_decode_with_raw(data, pos)
            result.append(item)
            raw_parts.append(raw)
        raw_parts.append(b"e")
        return result, pos + 1, b"".join(raw_parts)
    elif ch == b"d":
        result = {}
        pos += 1
        raw_parts = [b"d"]
        while data[pos:pos + 1] != b"e":
            key, pos, kr = _bencode_decode_with_raw(data, pos)
            val, pos, vr = _bencode_decode_with_raw(data, pos)
            result[key] = val
            raw_parts.extend([kr, vr])
        raw_parts.append(b"e")
        return result, pos + 1, b"".join(raw_parts)
    elif ch.isdigit():
        colon = data.index(b":", pos)
        length = int(data[pos:colon])
        s = colon + 1
        end = s + length
        return data[s:end], end, data[start:end]
    else:
        raise ValueError(f"Invalid bencode at pos {pos}: {ch!r}")


def _decode_str(v) -> str:
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.decode("latin-1")
    return str(v)


def parse_torrent(data: bytes) -> dict:
    decoded, _, _ = _bencode_decode_with_raw(data)
    if not isinstance(decoded, dict):
        raise ValueError("Torrent file root is not a dict")

    info_key = b"info"
    if info_key not in decoded:
        raise ValueError("No 'info' dict in torrent")

    raw_info = decoded[info_key]
    if not isinstance(raw_info, dict):
        raise ValueError("'info' is not a dict")

    # info_hash = SHA1 of the RAW bencoded info dict (NOT re-encoded)
    # Re-encoding would sort keys, changing the hash
    info_prefix = b"4:info"
    info_start = data.index(info_prefix) + len(info_prefix)
    # Re-decode from info_start to get the end position of the info dict
    _, info_end, info_raw_bytes = _bencode_decode_with_raw(data, info_start)
    info_hash = hashlib.sha1(info_raw_bytes).hexdigest().upper()

    str_info = {}
    for k, v in raw_info.items():
        key = _decode_str(k) if isinstance(k, bytes) else k
        str_info[key] = v

    name = _decode_str(str_info.get("name", ""))

    files = []
    if "length" in str_info:
        total_length = int(str_info["length"])
        files.append({"path": name, "length": total_length})
    elif "files" in str_info:
        total_length = 0
        for f in str_info["files"]:
            path_parts = f.get(b"path", f.get("path", []))
            path_str = "/".join(_decode_str(p) for p in path_parts)
            flen = int(f.get(b"length", f.get("length", 0)))
            total_length += flen
            files.append({"path": path_str, "length": flen})
    else:
        total_length = 0

    return {
        "info_hash": info_hash,
        "name": name,
        "length": total_length,
        "files": sorted(files, key=lambda f: f["path"]),
    }


# ── Torrent download ───────────────────────────────────────────

def _load_cookies() -> dict[str, str]:
    cookies = {}
    for key, val in _env_matching("PT_COOKIE_").items():
        site_id = key[len("PT_COOKIE_"):].lower()
        cookies[site_id] = val
    return cookies


_SITE_MAP = {
    "1ptba": {"url": "https://1ptba.com", "needs_proxy": False},
    "btschool": {"url": "https://pt.btschool.club", "needs_proxy": True},
    "carpt": {"url": "https://carpt.net", "needs_proxy": True},
    "hdfans": {"url": "https://hdfans.org", "needs_proxy": False},
    "pttime": {"url": "https://www.pttime.org", "needs_proxy": False},
    "soulvoice": {"url": "https://pt.soulvoice.club", "needs_proxy": True},
    "zmpt": {"url": "https://zmpt.cc", "needs_proxy": True},
    "ptskit": {"url": "https://www.ptskit.org", "needs_proxy": True},
    "pthome": {"url": "https://pthome.org", "needs_proxy": True},
    "hdsky": {"url": "https://hdsky.me", "needs_proxy": True},
    "hdhome": {"url": "https://hdhome.org", "needs_proxy": True},
    "audiences": {"url": "https://audiences.me", "needs_proxy": True},
    "keepfrds": {"url": "https://pt.keepfrds.com", "needs_proxy": True},
    "ttg": {"url": "https://totheglory.im", "needs_proxy": True},
}


def download_torrent(download_url: str, site: str = "") -> bytes:
    if site == "mteam":
        return _download_mteam(download_url)

    cookies = _load_cookies()
    cookie_str = cookies.get(site.lower(), "")

    proxy_url = None
    site_cfg = _SITE_MAP.get(site.lower())
    if site_cfg and site_cfg["needs_proxy"]:
        proxy_url = _env("PT_PROXY")

    req = urllib.request.Request(download_url)
    if cookie_str:
        req.add_header("Cookie", cookie_str)
    req.add_header("User-Agent",
                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0.0.0 Safari/537.36")

    with using_proxy(proxy_url):
        opener = urllib.request.build_opener()
        with opener.open(req, timeout=30) as resp:
            ct = resp.headers.get("Content-Type", "")
            if not any(t in ct.lower() for t in ("bittorrent", "octet-stream")):
                raise RuntimeError(f"Invalid Content-Type for .torrent: {ct}")
            return resp.read()


def _download_mteam(download_url: str) -> bytes:
    proxy = _env("PT_PROXY")
    if not proxy:
        raise RuntimeError("PT_PROXY not set — M-Team requires proxy")

    req = urllib.request.Request(download_url)
    req.add_header("User-Agent", "Mozilla/5.0")
    with using_proxy(proxy):
        opener = urllib.request.build_opener()
        with opener.open(req, timeout=30) as resp:
            ct = resp.headers.get("Content-Type", "")
            if not any(t in ct.lower() for t in ("bittorrent", "octet-stream")):
                raise RuntimeError(f"Invalid Content-Type for M-Team .torrent: {ct}")
            return resp.read()


def _get_mteam_download_url(torrent_id: str) -> str:
    from mteam_api import get_download_url as mteam_dl_url
    api_key = _env("MTEAM_API_KEY", "")
    if not api_key:
        raise RuntimeError("MTEAM_API_KEY not set")
    url = mteam_dl_url(torrent_id, api_key)
    if not url:
        raise RuntimeError(f"Failed to get M-Team download URL for {torrent_id}")
    return url


# ── Verification pipeline ──────────────────────────────────────

def _compare_files(base_files: list[dict], candidate_files: list[dict]) -> str:
    if not base_files or not candidate_files:
        return "MISSING_FILES"

    base_set = {(f["path"], f["length"]) for f in base_files}
    cand_set = {(f["path"], f["length"]) for f in candidate_files}

    if base_set == cand_set:
        return "VERIFIED"

    missing = base_set - cand_set
    if not missing:
        return "VERIFIED"

    return "MISSING_FILES"


def verify_torrents(items: list[dict]) -> list[dict]:
    if not items:
        return []

    base = items[0]
    all_items = [base] + items[1:]

    # Download and parse base torrent
    base_torrent = _fetch_and_parse(base)
    if base_torrent is None:
        for item in all_items:
            item["verified"] = False
            item["match_type"] = "download_failed"
        return all_items

    base["info_hash"] = base_torrent["info_hash"]
    base["verified"] = True
    base["match_type"] = "base"

    for candidate in items[1:]:
        cand_torrent = _fetch_and_parse(candidate)
        if cand_torrent is None:
            candidate["verified"] = False
            candidate["match_type"] = "download_failed"
            continue

        candidate["info_hash"] = cand_torrent["info_hash"]

        # Tier 1: info_hash match
        if cand_torrent["info_hash"] == base_torrent["info_hash"]:
            candidate["verified"] = True
            candidate["match_type"] = "info_hash"
            continue

        # Tier 2: name + length match
        if (cand_torrent["name"] == base_torrent["name"]
                and cand_torrent["length"] == base_torrent["length"]):
            result = _compare_files(base_torrent["files"], cand_torrent["files"])
            candidate["verified"] = result == "VERIFIED"
            candidate["match_type"] = "name_size"
            continue

        # Tier 3: file list comparison
        result = _compare_files(base_torrent["files"], cand_torrent["files"])
        candidate["verified"] = result == "VERIFIED"
        candidate["match_type"] = "files"

    return all_items


def _fetch_and_parse(item: dict) -> dict | None:
    download_url = item.get("download_url", "")
    site = item.get("site", item.get("source", "")).lower()

    if site == "mteam":
        torrent_id = item.get("id", "")
        if torrent_id and not download_url:
            try:
                download_url = _get_mteam_download_url(torrent_id)
            except Exception:
                return None

    if not download_url:
        return None

    try:
        raw = download_torrent(download_url, site)
        return parse_torrent(raw)
    except Exception:
        return None


# ── Task storage ───────────────────────────────────────────────

def _load_tasks() -> dict:
    if not os.path.exists(TASKS_FILE):
        return {}
    with open(TASKS_FILE) as f:
        return json.load(f)


def _save_tasks(tasks: dict):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def _gen_task_id() -> str:
    ts = int(time.time())
    import random
    suffix = random.randint(1000, 9999)
    return f"{ts}-{suffix}"


def create_task(title: str, items: list[dict], save_path: str) -> dict:
    tasks = _load_tasks()
    task_id = _gen_task_id()

    verified_items = [i for i in items if i.get("verified")]
    total_size = sum(i.get("size", i.get("size_bytes", 0)) for i in verified_items)

    task = {
        "id": task_id,
        "time": int(time.time()),
        "title": title,
        "size": total_size,
        "save_path": save_path,
        "items": items,
    }

    tasks[task_id] = task
    _save_tasks(tasks)
    return task


def list_tasks() -> list[dict]:
    tasks = _load_tasks()
    result = []
    for tid, task in sorted(tasks.items(), key=lambda x: x[1].get("time", 0), reverse=True):
        verified = sum(1 for i in task.get("items", []) if i.get("verified"))
        total = len(task.get("items", []))
        result.append({
            "task_id": tid,
            "title": task.get("title", ""),
            "time": task.get("time", 0),
            "size": _fmt_size(task.get("size", 0)),
            "items_total": total,
            "items_verified": verified,
            "save_path": task.get("save_path", ""),
        })
    return result


def delete_task(task_id: str) -> dict:
    tasks = _load_tasks()
    if task_id not in tasks:
        return {"error": f"Task {task_id} not found"}
    del tasks[task_id]
    _save_tasks(tasks)
    return {"deleted": task_id}


# ── qBittorrent integration (inline session) ──────────────────

_qb_opener = None
_qb_url = None


def _qb_get_opener():
    global _qb_opener, _qb_url
    if _qb_opener is not None:
        return _qb_opener

    _qb_url = _env("QBITTORRENT_URL", "").rstrip("/")
    qb_user = _env("QBITTORRENT_USER", "")
    qb_pass = _env("QBITTORRENT_PASS", "")

    cj = CookieJar()
    _qb_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    _qb_opener.addheaders = [("User-Agent", "Hermes/1.0")]
    login_data = urllib.parse.urlencode({"username": qb_user, "password": qb_pass}).encode()
    try:
        _qb_opener.open(f"{_qb_url}/api/v2/auth/login", login_data, timeout=10)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError("qBittorrent login failed — check QBITTORRENT_USER/PASS")
        raise
    return _qb_opener


def _qb_request(endpoint: str, method: str = "GET", data: dict = None):
    opener = _qb_get_opener()
    full_url = f"{_qb_url}{endpoint}"
    if method == "POST" and data:
        encoded = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(full_url, data=encoded, method=method)
    elif method == "POST":
        req = urllib.request.Request(full_url, method=method)
    else:
        req = urllib.request.Request(full_url, method=method)

    try:
        with opener.open(req, timeout=30) as resp:
            raw = resp.read()
            if not raw.strip():
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw.decode("utf-8", errors="replace").strip()}
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e}"}


def _qb_add_torrent_paused(download_url: str, save_path: str, tags: list[str]) -> dict:
    data = {
        "urls": download_url,
        "paused": "true",
    }
    if save_path:
        data["savepath"] = save_path
    if tags:
        data["tags"] = ",".join(tags)

    result = _qb_request("/api/v2/torrents/add", method="POST", data=data)
    if isinstance(result, dict) and "error" in result:
        return result
    return {"success": True, "message": f"Added paused: {download_url[:80]}"}


def _qb_get_completed() -> list[dict]:
    resp = _qb_request("/api/v2/torrents/info?filter=completed")
    if isinstance(resp, dict) and "error" in resp:
        raise RuntimeError(f"Failed to fetch completed torrents: {resp['error']}")
    return resp if isinstance(resp, list) else []


# ── Send task to qB ────────────────────────────────────────────

def send_task(task_id: str, base_only: bool = False, others_only: bool = False) -> dict:
    tasks = _load_tasks()
    if task_id not in tasks:
        return {"error": f"Task {task_id} not found"}

    task = tasks[task_id]
    items = task.get("items", [])
    save_path = task.get("save_path", "")

    if base_only:
        items = [items[0]] if items else []
    elif others_only:
        items = items[1:] if len(items) > 1 else []

    results = []
    for item in items:
        if not item.get("verified"):
            results.append({"site": item.get("site", ""), "status": "skipped", "reason": "not verified"})
            continue

        download_url = item.get("download_url", "")
        site = item.get("site", item.get("source", "")).lower()

        if site == "mteam" and not download_url:
            torrent_id = item.get("id", "")
            if torrent_id:
                try:
                    download_url = _get_mteam_download_url(torrent_id)
                except Exception as e:
                    results.append({"site": site, "status": "error", "reason": str(e)})
                    continue

        if not download_url:
            results.append({"site": site, "status": "error", "reason": "no download_url"})
            continue

        tags = [site, "cross-seed"]
        add_result = _qb_add_torrent_paused(download_url, save_path, tags)
        add_result["site"] = site
        add_result["title"] = item.get("title", "")
        results.append(add_result)

    return {"task_id": task_id, "results": results}


# ── Batch scan ─────────────────────────────────────────────────

def _clean_torrent_name(name: str) -> str:
    name = re.sub(r'^\[.*?\]\s*', '', name)
    name = re.sub(r'^[【].*?[】]\s*', '', name)
    name = re.sub(r'-\s*(MTeam|mteam|PTT|TTG|HDS|HDC|CHD|FRDS|HDHome|HDFans)\s*$', '', name, flags=re.IGNORECASE)
    return name.strip()


def _names_match(name1, name2):
    """Check if two torrent names refer to the same release.

    Cleans both names and returns True if they are identical
    or one contains the other (for partial matches).
    """
    c1 = _clean_torrent_name(name1).lower()
    c2 = _clean_torrent_name(name2).lower()
    if not c1 or not c2:
        return False
    if c1 == c2:
        return True
    if c1 in c2 or c2 in c1:
        return True
    return False


def batch_scan(sites: list[str] = None, limit: int = 50) -> list[dict]:
    completed = _qb_get_completed()
    if not completed:
        return []

    search_script = os.path.join(_skill_dir, "pt_search.py")
    opportunities = []
    seen_queries = set()

    for torrent in completed[:limit]:
        raw_name = torrent.get("name", "")
        query = _clean_torrent_name(raw_name)
        if not query or len(query) < 4:
            continue
        if query in seen_queries:
            continue
        seen_queries.add(query)

        existing_hash = torrent.get("hash", "").upper()
        existing_size = torrent.get("size", 0)
        save_path = torrent.get("save_path", torrent.get("content_path", ""))

        site_suffix = ",".join(sites) if sites else "all"
        cached = cache_get(f"batch-{site_suffix}", query)
        if cached is not None:
            search_results = cached
        else:
            cmd = ["python3", search_script, query, "--limit", "10"]
            if sites:
                for s in sites:
                    cmd.extend(["--site", s])

            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                                   env=os.environ.copy())
                if r.returncode != 0 or not r.stdout.strip():
                    continue
                data = json.loads(r.stdout)
            except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
                continue

            search_results = data.get("results", []) if isinstance(data, dict) else data
            cache_put(f"batch-{site_suffix}", query, search_results)
        candidates = []

        for sr in search_results:
            if "error" in sr:
                continue
            sr_size = sr.get("size_bytes", 0)
            if sr_size == 0:
                sr_size = _parse_size_str(sr.get("size", ""))

            sr_site = sr.get("source", sr.get("site_id", sr.get("site", ""))).lower()
            sr_dl_url = sr.get("download_url", "")

            if sr_site == "mteam" and not sr_dl_url:
                tid = sr.get("id", "")
                if tid:
                    try:
                        sr_dl_url = _get_mteam_download_url(tid)
                    except Exception:
                        continue

            if not sr_dl_url:
                continue

            cand_torrent = None
            try:
                raw = download_torrent(sr_dl_url, sr_site)
                cand_torrent = parse_torrent(raw)
            except Exception:
                continue

            # Tier 1: exact info_hash match
            if cand_torrent["info_hash"] == existing_hash:
                candidates.append({
                    "site": sr_site,
                    "title": sr.get("title", ""),
                    "info_hash": cand_torrent["info_hash"],
                    "match_type": "info_hash",
                    "download_url": sr_dl_url,
                    "seeders": sr.get("seeders", 0),
                    "promo": sr.get("promo", ""),
                })
                continue

            # Tier 2: name match + size within 5% + file list match
            if existing_size > 0 and sr_size > 0:
                cand_name = cand_torrent["name"]
                sr_title = sr.get("title", "")
                name_ok = (_names_match(cand_name, raw_name)
                           or (sr_title and _names_match(sr_title, raw_name)))
                if name_ok:
                    size_ratio = sr_size / existing_size
                    if 0.95 <= size_ratio <= 1.05:
                        result = _compare_files(
                            [{"path": "", "length": existing_size}],
                            [{"path": "", "length": sr_size}],
                        )
                        if result == "VERIFIED" or cand_torrent["length"] == existing_size:
                            candidates.append({
                                "site": sr_site,
                                "title": sr.get("title", ""),
                                "info_hash": cand_torrent["info_hash"],
                                "match_type": "name_size",
                                "download_url": sr_dl_url,
                                "seeders": sr.get("seeders", 0),
                                "promo": sr.get("promo", ""),
                            })

        if candidates:
            opportunities.append({
                "existing_name": raw_name,
                "existing_hash": existing_hash,
                "existing_size": existing_size,
                "save_path": save_path,
                "candidates": candidates,
            })

    return opportunities


def _parse_size_str(size_str: str) -> int:
    m = re.match(r'([\d.]+)\s*(TB|GB|MB|KB|B)', size_str, re.IGNORECASE)
    if not m:
        return 0
    val = float(m.group(1))
    unit = m.group(2).upper()
    mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return int(val * mult.get(unit, 1))


# ── CLI ────────────────────────────────────────────────────────

def _parse_args(argv: list[str]) -> dict:
    args = {"positional": [], "flags": {}}
    skip = False
    for i, a in enumerate(argv):
        if skip:
            skip = False
            continue
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                args["flags"][key] = argv[i + 1]
                skip = True
            else:
                args["flags"][key] = True
        else:
            args["positional"].append(a)
    return args


def main():
    argv = sys.argv[1:]

    if not argv or "--help" in argv or "-h" in argv:
        print(__doc__)
        sys.exit(0)

    cmd = argv[0]
    parsed = _parse_args(argv[1:])

    if cmd == "verify":
        if "stdin" in parsed["flags"]:
            raw = sys.stdin.read()
            items = json.loads(raw)
            if isinstance(items, dict) and "results" in items:
                items = items["results"]
        else:
            input_path = parsed["flags"].get("input", "")
            if not input_path:
                print(json.dumps({"error": "--input <file> or --stdin required"}))
                sys.exit(1)
            with open(input_path) as f:
                items = json.load(f)
        if not isinstance(items, list):
            print(json.dumps({"error": "Input must be a JSON array of search results"}))
            sys.exit(1)
        results = verify_torrents(items)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif cmd == "create-task":
        title = parsed["flags"].get("title", "")
        save_path = parsed["flags"].get("save-path", "")
        if "stdin" in parsed["flags"]:
            items = json.loads(sys.stdin.read())
            if isinstance(items, dict) and "results" in items:
                items = items["results"]
        else:
            items_path = parsed["flags"].get("items", "")
            if not title or not items_path:
                print(json.dumps({"error": "--title and --items required (or use --stdin)"}))
                sys.exit(1)
            with open(items_path) as f:
                items = json.load(f)
        if not title:
            print(json.dumps({"error": "--title required"}))
            sys.exit(1)
        task = create_task(title, items, save_path)
        print(json.dumps({"task_id": task["id"], "title": task["title"],
                          "items": len(task["items"]),
                          "verified": sum(1 for i in task["items"] if i.get("verified"))},
                         ensure_ascii=False, indent=2))

    elif cmd == "list":
        tasks = list_tasks()
        print(json.dumps(tasks, ensure_ascii=False, indent=2))

    elif cmd == "send":
        task_id = parsed["flags"].get("task-id", "")
        if not task_id:
            print(json.dumps({"error": "--task-id required"}))
            sys.exit(1)
        base_only = "base-only" in parsed["flags"]
        others_only = "others-only" in parsed["flags"]
        result = send_task(task_id, base_only=base_only, others_only=others_only)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "delete":
        task_id = parsed["flags"].get("task-id", "")
        if not task_id:
            print(json.dumps({"error": "--task-id required"}))
            sys.exit(1)
        result = delete_task(task_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "search":
        query = " ".join(parsed["positional"]) or parsed["flags"].get("query", "")
        save_path = parsed["flags"].get("save-path", "")
        site = parsed["flags"].get("site", "")
        if not query:
            print(json.dumps({"error": "Search query required"}))
            sys.exit(1)
        search_script = os.path.join(_skill_dir, "pt_search.py")
        cmd_args = ["python3", search_script, query, "--limit", "20"]
        if site:
            cmd_args.extend(["--site", site])
        r = subprocess.run(cmd_args, capture_output=True, text=True, timeout=60,
                           env=os.environ.copy())
        if r.returncode != 0 or not r.stdout.strip():
            print(json.dumps({"error": "Search failed", "detail": r.stderr[:200]}))
            sys.exit(1)
        data = json.loads(r.stdout)
        results = data.get("results", []) if isinstance(data, dict) else data
        if not results:
            print(json.dumps({"query": query, "verified": 0, "message": "No results found"}))
            return
        verified = verify_torrents(results)
        verified_count = sum(1 for i in verified if i.get("verified"))
        if verified_count < 2:
            print(json.dumps({"query": query, "results": len(results),
                              "verified": verified_count,
                              "message": "Need at least 2 verified items for cross-seed"},
                             ensure_ascii=False, indent=2))
            return
        task = create_task(query, verified, save_path)
        print(json.dumps({"query": query, "task_id": task["id"],
                          "verified": verified_count, "total": len(results),
                          "save_path": save_path}, ensure_ascii=False, indent=2))

    elif cmd == "batch-scan":
        site_str = parsed["flags"].get("site", "")
        sites = [s.strip() for s in site_str.split(",") if s.strip()] if site_str else None
        limit = int(parsed["flags"].get("limit", "50"))
        results = batch_scan(sites=sites, limit=limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
