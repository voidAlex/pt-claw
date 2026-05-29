#!/usr/bin/env python3
"""
Search Sukebei Nyaa for JAV magnets via RSS.

Usage:
    python3 sukebei_search.py SNOS-151              # search by code
    python3 sukebei_search.py SNOS-151 --limit 5    # limit results

Output: JSON array with seeders, leechers, size, magnet link, title.
"""

import sys, json, os, re, urllib.request, urllib.parse
from xml.etree import ElementTree as ET

ENV_FILE = os.path.expanduser("~/.hermes/.env")
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

SUKEBEI_RSS = "https://sukebei.nyaa.si/?page=rss"
NYAA_NS = "https://sukebei.nyaa.si/xmlns/nyaa"

# ── Ad / spam filter ──────────────────────────────────────────
AD_KEYWORDS = [
    "加群", "QQ", "微信", "tg", "广告", "推广", "福利", "免费", "导航",
    "合集", "大合集", "まとめ", "pack", "collection", "全作品",
    "预告", "宣传片", "sample", "trailer", "预览",
]
PREFERRED_TAGS = ["FHDC", "HD", "4K", "中文字幕", "H265", "HEVC", "uncensored",
                  "破解", "無碼", "Reducing Mosaic", "破坏版", "破壊版", "RM", "leak"]


def is_spam(title: str) -> bool:
    """Filter out ads, compilations, and previews."""
    for kw in AD_KEYWORDS:
        if kw.lower() in title.lower():
            return True
    # Skip hash-only or garbled titles
    if re.match(r'^[a-f0-9]{40}$', title.strip(), re.I):
        return True
    return False


def score(title: str) -> int:
    """Higher score = better match. Prefer known tags."""
    s = 0
    for tag in PREFERRED_TAGS:
        if tag.lower() in title.lower():
            s += 1
    return s


def search(code: str, limit: int = 20) -> list[dict]:
    """Search Sukebei Nyaa RSS for a JAV code. Returns deduplicated results."""
    url = f"{SUKEBEI_RSS}&q={urllib.parse.quote(code)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
    proxy = _env("PT_PROXY")

    if proxy:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        opener = urllib.request.build_opener(proxy_handler)
    else:
        opener = urllib.request.build_opener()

    try:
        with opener.open(req, timeout=15) as resp:
            root = ET.fromstring(resp.read())
    except Exception as e:
        return [{"error": str(e), "source": "sukebei"}]

    results = []
    seen_hashes = set()

    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        seeders_el = item.find(f"{{{NYAA_NS}}}seeders")
        leechers_el = item.find(f"{{{NYAA_NS}}}leechers")
        size_el = item.find(f"{{{NYAA_NS}}}size")
        info_hash_el = item.find(f"{{{NYAA_NS}}}infoHash")

        title = title_el.text if title_el is not None else ""
        ih = info_hash_el.text if info_hash_el is not None else ""

        if is_spam(title):
            continue
        if ih.upper() in seen_hashes:
            continue
        seen_hashes.add(ih.upper())

        results.append({
            "title": title.strip(),
            "magnet": f"magnet:?xt=urn:btih:{ih}&dn={urllib.parse.quote(title)}",
            "info_hash": ih,
            "seeders": int(seeders_el.text) if seeders_el is not None and seeders_el.text and seeders_el.text.strip() else 0,
            "leechers": int(leechers_el.text) if leechers_el is not None and leechers_el.text and leechers_el.text.strip() else 0,
            "size": size_el.text if size_el is not None else "?",
            "torrent_url": link_el.text if link_el is not None else "",
            "score": score(title),
            "source": "sukebei",
        })

    # Sort: seeders desc, score desc
    results.sort(key=lambda r: (-r["seeders"], -r["score"]))
    return results[:limit]


def main():
    if len(sys.argv) < 2:
        print("Usage: sukebei_search.py <CODE> [--limit N]", file=sys.stderr)
        sys.exit(1)

    code = sys.argv[1]
    limit = 20
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])

    results = search(code, limit)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
