#!/usr/bin/env python3
"""
Jellyfin utility — query libraries, count stars, cross-reference.

Usage:
    python3 jf_query.py --list libs                           # list libraries
    python3 jf_query.py --list stars --top 20                 # top N stars by count
    python3 jf_query.py --search "浅野"                        # search movies
    python3 jf_query.py --check "ROYD-318"                     # check if code exists

Env: reads JELLYFIN1_URL / JELLYFIN1_API_KEY from secrets.env
     Pass --server 1|2 to select JF1/JF2 (default: 1)
"""

import json, os, sys, urllib.request, urllib.parse
from collections import Counter

def get_env(key):
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "secrets.env")
    val = os.environ.get(key, "")
    if not val and os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if line.startswith(key + "="):
                    val = line.split("=", 1)[1].strip()
                    break
    return val

def parse_arg(args, flag, default=None):
    for i, a in enumerate(args):
        if a == flag and i + 1 < len(args):
            return args[i + 1]
    return default

def flag_present(args, flag):
    return flag in args

def jf_get(endpoint, server=1):
    url = get_env(f"JELLYFIN{server}_URL")
    key = get_env(f"JELLYFIN{server}_API_KEY")
    if not url or not key:
        return {"error": f"JELLYFIN{server} not configured"}
    req = urllib.request.Request(f"{url}{endpoint}", headers={"X-MediaBrowser-Token": key})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def main():
    args = sys.argv[1:]

    if flag_present(args, "--help") or flag_present(args, "-h"):
        print(__doc__)
        sys.exit(0)

    server = int(parse_arg(args, "--server", "1"))

    # --- List modes ---
    if flag_present(args, "--list"):
        list_what = parse_arg(args, "--list", "libs")

        if list_what == "libs":
            libs = jf_get("/Library/VirtualFolders", server)
            for lib in libs:
                print(f"  {lib['Name']:>8} ({lib.get('CollectionType','?')}) id={lib['ItemId']}")
            sys.exit(0)

        if list_what == "stars":
            top_n = int(parse_arg(args, "--top", "20"))
            # Find movies library
            libs = jf_get("/Library/VirtualFolders", server)
            movie_lib = None
            for lib in libs:
                if lib.get('CollectionType') == 'movies':
                    movie_lib = lib['ItemId']
                    break
            if not movie_lib:
                print(json.dumps({"error": "No movie library found"}))
                sys.exit(1)

            star_count = Counter()
            total = 0
            start = 0
            limit = 200
            while True:
                url = f"/Items?parentId={movie_lib}&recursive=true&includeItemTypes=Movie&fields=People&startIndex={start}&limit={limit}"
                data = jf_get(url, server)
                items = data.get("Items", [])
                if not items:
                    break
                for item in items:
                    total += 1
                    for p in item.get("People", []):
                        if p.get("Type") == "Actor":
                            star_count[p["Name"]] += 1
                start += limit
                if start >= data.get("TotalRecordCount", 0):
                    break

            result = {"total_movies": total, "total_stars": len(star_count), "top": []}
            for name, cnt in star_count.most_common(top_n):
                result["top"].append({"name": name, "count": cnt})
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(0)

    # --- Search mode ---
    if flag_present(args, "--search"):
        keyword = parse_arg(args, "--search")
        data = jf_get(f"/Items?searchTerm={urllib.parse.quote(keyword)}&recursive=true&includeItemTypes=Movie", server)
        items = data.get("Items", [])
        result = {"query": keyword, "total": data.get("TotalRecordCount", 0), "items": []}
        for item in items[:20]:
            result["items"].append({
                "name": item.get("Name", ""),
                "year": item.get("ProductionYear", ""),
            })
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    # --- Check mode ---
    if flag_present(args, "--check"):
        code = parse_arg(args, "--check")
        data = jf_get(f"/Items?searchTerm={urllib.parse.quote(code)}&recursive=true", server)
        result = {"code": code, "found": data.get("TotalRecordCount", 0) > 0, "count": data.get("TotalRecordCount", 0)}
        print(json.dumps(result))
        sys.exit(0)

    print(__doc__)

if __name__ == "__main__":
    main()
