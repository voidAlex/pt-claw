#!/usr/bin/env python3
"""
Search Sukebei Nyaa for JAV magnets via RSS.

Usage:
    python3 sukebei_search.py SNOS-151              # search by code
    python3 sukebei_search.py SNOS-151 --limit 5    # limit results

Output: JSON array with seeders, leechers, size, magnet link, title.
"""

import sys, json, os, urllib.request, urllib.parse
from xml.etree import ElementTree as ET

from _common import _env, _is_spam as is_spam, _magnet_score as score
from _proxy import using_proxy

SUKEBEI_RSS = "https://sukebei.nyaa.si/?page=rss"
NYAA_NS = "https://sukebei.nyaa.si/xmlns/nyaa"


def search(code: str, limit: int = 20) -> list[dict]:
    """Search Sukebei Nyaa RSS for a JAV code. Returns deduplicated results."""
    url = f"{SUKEBEI_RSS}&q={urllib.parse.quote(code)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
    proxy = _env("PT_PROXY")

    with using_proxy(proxy):
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
