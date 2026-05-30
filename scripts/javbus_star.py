#!/usr/bin/env python3
"""
Cross-reference actress filmography: javbus-api → JF + download history.

Usage:
    python3 javbus_star.py "彩月七緒"                # search by Chinese/Japanese name
    python3 javbus_star.py --star-id 11wm             # search by star ID directly
    python3 javbus_star.py "浅野こころ" --top 10      # show top 10 missing

Output: JSON with existing (in JF or history) and missing films, sorted by date.
"""

import json, os, sys, re, urllib.request, urllib.parse

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
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                _env_cache[k.strip()] = v.strip()

def _env(key, default=""):
    val = os.environ.get(key, "")
    if not val:
        _load_env_file()
        val = _env_cache.get(key, default)
    return val

JAVBUS_API = _env("JAVBUS_API_URL") or "http://localhost:8922"

def _make_opener():
    proxy = _env("PT_PROXY")
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    return urllib.request.build_opener()

def javbus_get(path):
    req = urllib.request.Request(f"{JAVBUS_API}{path}",
                                 headers={"User-Agent": "Hermes/1.0"})
    with _make_opener().open(req, timeout=15) as r:
        return json.loads(r.read())

def jf_check(code, server=1):
    url = _env(f"JELLYFIN{server}_URL")
    key = _env(f"JELLYFIN{server}_API_KEY")
    if not url or not key:
        return False
    try:
        q = urllib.parse.quote(code)
        req = urllib.request.Request(f"{url}/Items?searchTerm={q}&recursive=true",
                                     headers={"X-MediaBrowser-Token": key,
                                               "User-Agent": "Hermes/1.0"})
        with urllib.request.build_opener().open(req, timeout=5) as r:
            return json.loads(r.read()).get("TotalRecordCount", 0) > 0
    except Exception:
        return False

def load_history():
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pt_downloaded.json")
    if not os.path.exists(f):
        return set()
    with open(f) as fh:
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
            break
        for m in movies:
            # Only include if this star is in the cast
            try:
                detail = javbus_get(f"/api/movies/{m['id']}")
            except Exception:
                continue
            for s in detail.get("stars", []):
                if s["id"] == star_id:
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

    result = {
        "star": {"id": star_id, "name": star_name},
        "total": len(all_films),
        "existing": len(existing),
        "missing": len(missing),
        "existing_films": existing,
        "missing_films": missing,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
