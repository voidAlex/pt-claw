#!/usr/bin/env python3
"""
Search JavBus for magnets via local javbus-api or raw scraping.

Usage:
    # With javbus-api deployed (recommended):
    python3 javbus_magnet.py SNOS-151 --api http://localhost:8922

    # Raw scraping (no API needed):
    python3 javbus_magnet.py SNOS-151 --scrape

Output: JSON array with title, magnet, size, isHD, hasSubtitle, shareDate.
"""

import sys, json, os, re, urllib.request, urllib.parse

from _common import _env, _is_spam, _magnet_score as _score
from _proxy import using_proxy


# ── javbus-api client ─────────────────────────────────────────
def search_api(code: str, api_url: str) -> dict:
    """Get movie details + magnets via javbus-api."""
    base = api_url.rstrip("/")

    # Step 1: movie details
    detail_url = f"{base}/api/movies/{urllib.parse.quote(code)}"
    detail = _get_json(detail_url)
    if not detail or "gid" not in detail:
        return {"error": f"Movie not found: {code}", "source": "javbus-api"}

    gid = detail["gid"]
    uc = detail.get("uc", "0")

    # Step 2: magnets + filter
    magnet_url = f"{base}/api/magnets/{urllib.parse.quote(code)}?gid={gid}&uc={uc}&sortBy=size&sortOrder=desc"
    raw_magnets = _get_json(magnet_url) or []
    magnets = [
        m for m in raw_magnets
        if not _is_spam(m.get("title", ""))
    ]
    for m in magnets:
        m["score"] = _score(m.get("title", ""))

    return {
        "code": code,
        "title": detail.get("title", ""),
        "cover": detail.get("img", ""),
        "date": detail.get("date", ""),
        "stars": [s["name"] for s in detail.get("stars", [])],
        "samples": detail.get("samples", []),
        "magnets": magnets,
        "source": "javbus-api",
    }


# ── Raw scraping fallback ─────────────────────────────────────
def search_scrape(code: str) -> dict:
    """Scrape JavBus directly (no API deployment needed)."""
    proxy = _env("PT_PROXY")

    # Step 1: get page + gid
    html = _fetch(f"https://www.javbus.com/{code}", proxy)
    gid_match = re.search(r'var gid = (\d+)', html)
    uc_match = re.search(r'var uc = (\d+)', html)
    if not gid_match:
        return {"error": f"Movie not found: {code}", "source": "javbus-scrape"}

    gid = gid_match.group(1)
    uc = uc_match.group(1) if uc_match else "0"

    # Cover
    cover_match = re.search(r'class="bigImage"[^>]*href="([^"]+)"', html)
    cover = cover_match.group(1) if cover_match else ""

    # Samples (preview images)
    samples = re.findall(r'https://pics\.dmm\.co\.jp[^"]+\.jpg', html)

    # Step 2: Ajax magnets
    ajax_url = (
        f"https://www.javbus.com/ajax/uncledatoolsbyajax.php"
        f"?gid={gid}&lang=zh&img=https://pics.javbus.com/cover/xxx.jpg&uc={uc}"
    )
    html = _fetch(ajax_url, proxy, referer=f"https://www.javbus.com/{code}")

    # Step 3: extract + deduplicate magnets
    seen = set()
    magnets = []
    for m in re.finditer(
        r'magnet:\?xt=urn:btih:([a-f0-9A-F]{40})(?:&dn=([^&\'\"\]]+))?', html
    ):
        ih = m.group(1).upper()
        if ih in seen:
            continue
        dn = urllib.parse.unquote(m.group(2) or "")
        if _is_spam(dn):
            continue
        seen.add(ih.upper())

        # Try to extract size from nearby text
        size_match = re.search(
            r'(\d+\.?\d*)\s*(GB|MB)', html[m.end(): m.end() + 300]
        )
        size = size_match.group(0) if size_match else "?"

        # Check for HD / subtitle flags
        after = html[m.end(): m.end() + 300]
        is_hd = "高清" in after or "HD" in after
        has_sub = "字幕" in after or "subtitle" in after.lower()

        magnets.append({
            "title": dn,
            "link": m.group(0),
            "size": size,
            "isHD": is_hd,
            "hasSubtitle": has_sub,
            "score": _score(dn),
        })

    return {
        "code": code,
        "cover": cover,
        "samples": [{"src": s} for s in samples[:10]],
        "gid": gid,
        "uc": uc,
        "magnets": magnets,
        "source": "javbus-scrape",
    }


# ── Helpers ───────────────────────────────────────────────────
def _get_json(url: str) -> dict | list | None:
    proxy = _env("PT_PROXY") or None
    req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
    try:
        with using_proxy(proxy):
            opener = urllib.request.build_opener()
            with opener.open(req, timeout=15) as r:
                return json.loads(r.read())
    except Exception:
        return None


def _fetch(url: str, proxy: str = "", referer: str = "") -> str:
    headers = {"User-Agent": "Hermes/1.0"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with using_proxy(proxy or None):
        opener = urllib.request.build_opener()
        try:
            with opener.open(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            return ""


def main():
    if len(sys.argv) < 2:
        print("Usage: javbus_magnet.py <CODE> [--api URL | --scrape]", file=sys.stderr)
        print("  --api URL   Use deployed javbus-api (e.g. http://localhost:8922)", file=sys.stderr)
        print("  --scrape    Raw scrape JavBus (no API needed, less structured)", file=sys.stderr)
        sys.exit(1)

    code = sys.argv[1]

    if "--api" in sys.argv:
        idx = sys.argv.index("--api")
        api_url = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else _env("JAVBUS_API_URL", "http://localhost:8922")
        result = search_api(code, api_url)
    elif _env("JAVBUS_API_URL"):
        result = search_api(code, _env("JAVBUS_API_URL"))
    else:
        result = search_scrape(code)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
