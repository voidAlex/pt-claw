#!/usr/bin/env python3
"""
Cross-reference actress filmography: javbus-api → JF + download history.

Usage:
    python3 javbus_star.py "彩月七緒"                # search by Chinese/Japanese name
    python3 javbus_star.py --star-id 11wm             # search by star ID directly
    python3 javbus_star.py "浅野こころ" --top 10      # show top 10 missing

Output: JSON with existing (in JF or history) and missing films, sorted by date.
"""

import json, os, sys, re, urllib.parse

from _common import _env
from _http import fetch_json
from _logger import get_logger

log = get_logger("javbus_star")

JAVBUS_API = (_env("JAVBUS_API_URL") or "http://localhost:8922").rstrip("/")

def javbus_get(path):
    # javbus-api 是本地服务（默认 localhost:8922），禁止套 PT_PROXY——
    # 代理会把 localhost 解析成代理机自身 → 必然 502（2026-08-24 追剧静默故障根因）。
    # 仅当 JAVBUS_API_URL 配置为远程地址时才走代理。
    proxy = None
    host = urllib.parse.urlparse(JAVBUS_API).hostname or "localhost"
    if host not in ("localhost", "127.0.0.1", "::1"):
        proxy = _env("PT_PROXY") or None
    data, elapsed = fetch_json(f"{JAVBUS_API}{path}", proxy=proxy)
    return data

def jf_check(code, server=1):
    url = _env(f"JELLYFIN{server}_URL").rstrip("/")
    key = _env(f"JELLYFIN{server}_API_KEY")
    if not url or not key:
        return False
    try:
        q = urllib.parse.quote(code)
        data, elapsed = fetch_json(
            f"{url}/Items?searchTerm={q}&recursive=true",
            headers={"X-MediaBrowser-Token": key},
        )
        return data.get("TotalRecordCount", 0) > 0
    except Exception:
        return False

def load_history():
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pt_downloaded.json")
    if not os.path.exists(f):
        return set()
    with open(f, encoding="utf-8") as fh:
        return {i['code'] for i in json.load(fh).get('items', [])}

def main():
    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    top_n = None
    for i, a in enumerate(args):
        if a == "--top" and i + 1 < len(args):
            top_n = int(args[i + 1])

    # Resolve star ID
    star_id = None
    star_name = None
    for i, a in enumerate(args):
        if a == "--star-id" and i + 1 < len(args):
            star_id = args[i + 1]
            break

    if not star_id:
        star_name = args[0]
        log.info("resolving star name=%s", star_name)
        # Search javbus-api for the actress
        try:
            results = javbus_get(f"/api/movies/search?keyword={urllib.parse.quote(star_name)}&page=1")
        except Exception as e:
            print(json.dumps({"error": f"Network error searching for star: {e}"}, ensure_ascii=False))
            sys.exit(1)
        movies = results.get("movies", [])
        if not movies:
            print(json.dumps({"error": f"No results for '{star_name}'", "hint": "Try Japanese name"}, ensure_ascii=False))
            sys.exit(1)
        # Get star ID from first movie
        try:
            detail = javbus_get(f"/api/movies/{movies[0]['id']}")
        except Exception as e:
            print(json.dumps({"error": f"Network error fetching movie detail: {e}"}, ensure_ascii=False))
            sys.exit(1)
        stars = detail.get("stars", [])
        if not stars:
            print(json.dumps({"error": "No star info found"}))
            sys.exit(1)
        star_id = stars[0]["id"]
        star_name = stars[0]["name"]

    log.info("querying star name=%s id=%s", star_name, star_id)

    # Paginate through all movies by this star
    all_films = {}
    page = 1
    while True:
        search_kw = star_name if star_name else star_id
        try:
            results = javbus_get(f"/api/movies/search?keyword={urllib.parse.quote(search_kw)}&page={page}")
        except Exception as e:
            print(f"Warning: network error on page {page}: {e}", file=sys.stderr)
            break
        movies = results.get("movies", [])
        if not movies or page > 10:
            if page > 10:
                print(f"Warning: results truncated at page 10 for '{search_kw}'", file=sys.stderr)
            break
        for m in movies:
            # Only include if this star is in the cast
            try:
                detail = javbus_get(f"/api/movies/{m['id']}")
            except Exception:
                continue
            for s in detail.get("stars", []):
                if s["id"] == star_id:
                    if not star_name:
                        star_name = s.get("name", star_name)
                    all_films[m["id"]] = {
                        "code": m["id"],
                        "date": m.get("date", "?"),
                        "title": m.get("title", ""),
                    }
                    break
        page += 1

    # Cross-reference
    history = load_history()
    existing = []
    missing = []
    for code, info in sorted(all_films.items(), key=lambda x: x[1].get("date","9999"), reverse=True):
        entry = {**info}
        entry["sources"] = []
        if code in history:
            entry["sources"].append("history")
        if jf_check(code, 1):
            entry["sources"].append("JF1")
        if entry["sources"]:
            existing.append(entry)
        else:
            missing.append(entry)

    if top_n and missing:
        missing = missing[:top_n]

    log.info("star query done name=%s total=%d existing=%d missing=%d", star_name or star_id, len(all_films), len(existing), len(missing))

    result = {
        "star": {"id": star_id, "name": star_name or star_id},
        "total": len(all_films),
        "existing": len(existing),
        "missing": len(missing),
        "existing_films": existing,
        "missing_films": missing,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
