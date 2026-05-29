#!/usr/bin/env python3
"""
M-Team (馒头) API client — search and download token generation.

Usage:
    # Search
    python3 mteam_api.py search "关键词" --key YOUR_API_KEY [--limit 25]

    # Get download URL
    python3 mteam_api.py download <torrent_id> --key YOUR_API_KEY

Config from env:
    MTEAM_API_KEY — default API key

Details: references/mteam-api.md
"""

import sys, json, os, urllib.request

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
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    _env_cache[k.strip()] = v.strip()


def _env(key, default=""):
    val = os.environ.get(key, "")
    if not val:
        _load_env_file()
        val = _env_cache.get(key, default)
    return val


API_HOST = "https://api.m-team.cc/api"


def _api_post(endpoint: str, api_key: str, body: dict | None = None, timeout: int = 15) -> dict:
    """Make a POST request to M-Team API."""
    url = f"{API_HOST}{endpoint}"
    data = json.dumps(body or {}).encode() if body else b""

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("x-api-key", api_key)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"code": str(e.code), "message": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"code": "-1", "message": str(e)}


def search(keyword: str, api_key: str, limit: int = 25) -> list[dict]:
    """Search M-Team torrents. Returns list of results."""
    resp = _api_post("/torrent/search", api_key, {"keyword": keyword, "page": 1, "size": min(limit, 25)})

    if str(resp.get("code")) != "0":
        return [{"error": resp.get("message", "API error"), "source": "mteam"}]

    items = resp.get("data", {}).get("data", [])
    results = []

    for item in items:
        status = item.get("status", {})
        seeders = int(status.get("seeders", 0))
        leechers = int(status.get("leechers", 0))
        size_bytes = int(item.get("size", 0))
        size_str = _fmt_size(size_bytes)
        torrent_id = item.get("id", "")
        discount = status.get("discount", "")

        # Promo
        promo = ""
        if "PERCENT_50" in discount:
            promo = "50%"
        elif "PERCENT_30" in discount:
            promo = "30%"
        elif "FREE" in discount:
            promo = "Free"
        elif "TWOUP" in discount:
            promo = "2xUp"

        results.append({
            "id": torrent_id,
            "title": item.get("name", "").strip(),
            "size": size_str,
            "size_bytes": size_bytes,
            "seeders": seeders,
            "leechers": leechers,
            "category": str(item.get("category", "")),
            "promo": promo,
            "detail_url": f"https://www.m-team.cc/detail/{torrent_id}" if torrent_id else "",
            "source": "mteam",
        })

    results.sort(key=lambda r: r["seeders"], reverse=True)
    return results[:limit]


def get_download_url(torrent_id: str, api_key: str) -> str:
    """Generate a signed download URL for a torrent ID."""
    resp = _api_post(f"/torrent/genDlToken?id={torrent_id}", api_key, timeout=10)

    if str(resp.get("code")) != "0":
        return ""

    return resp.get("data", "")


def _fmt_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def main():
    if len(sys.argv) < 2:
        print("Usage:", file=sys.stderr)
        print("  mteam_api.py search <QUERY> --key KEY [--limit N]", file=sys.stderr)
        print("  mteam_api.py download <ID> --key KEY", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    api_key = _env("MTEAM_API_KEY", "")

    if "--key" in sys.argv:
        idx = sys.argv.index("--key")
        if idx + 1 < len(sys.argv):
            api_key = sys.argv[idx + 1]

    if not api_key:
        print(json.dumps({"error": "No API key. Set MTEAM_API_KEY env or use --key."}))
        sys.exit(1)

    if cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        limit = 25
        if "--limit" in sys.argv:
            idx = sys.argv.index("--limit")
            if idx + 1 < len(sys.argv):
                limit = int(sys.argv[idx + 1])
        results = search(query, api_key, limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif cmd == "download":
        torrent_id = sys.argv[2] if len(sys.argv) > 2 else ""
        dl_url = get_download_url(torrent_id, api_key)
        print(json.dumps({"torrent_id": torrent_id, "download_url": dl_url}))

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
