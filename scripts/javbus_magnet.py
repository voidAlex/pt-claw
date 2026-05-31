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

import sys, json, os, re, urllib.parse

from _common import _env, _is_spam, _magnet_score as _score
from _http import fetch, fetch_json


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

    html = _fetch_text(f"https://www.javbus.com/{code}", proxy)

    # Detect CAPTCHA or redirect before parsing
    if not html:
        return {"error": f"Empty response for {code} — site may be down", "source": "javbus-scrape"}
    if re.search(r'captcha|验证码|cloudflare', html, re.IGNORECASE):
        return {"error": f"CAPTCHA/Cloudflare challenge for {code}", "source": "javbus-scrape"}
    if re.search(r'<title[^>]*>.*?(?:302|301|redirect).*?</title>', html, re.IGNORECASE | re.DOTALL):
        return {"error": f"Redirected for {code} — movie may not exist", "source": "javbus-scrape"}
    gid_match = re.search(r'(?:var|let|const)\s+gid\s*=\s*(\d+)', html)
    uc_match = re.search(r'(?:var|let|const)\s+uc\s*=\s*(\d+)', html)
    if not gid_match:
        return {"error": f"Movie not found: {code}", "source": "javbus-scrape"}

    gid = gid_match.group(1)
    uc = uc_match.group(1) if uc_match else "0"

    # Cover
    cover_match = re.search(r'class="[^"]*bigImage[^"]*"[^>]*href="([^"]+)"', html)
    cover = cover_match.group(1) if cover_match else ""

    # Samples (preview images)
    # Match sample images from any CDN domain (not just pics.dmm.co.jp)
    samples = re.findall(r'https?://[^"\'\s]+/(?:pics|samples|digital)/[^"\'\s]+\.jpg', html, re.IGNORECASE)

    # Step 2: Ajax magnets
    ajax_url = (
        f"https://www.javbus.com/ajax/uncledatoolsbyajax.php"
        f"?gid={gid}&lang=zh&img=https://pics.javbus.com/cover/xxx.jpg&uc={uc}"
    )
    html = _fetch_text(ajax_url, proxy, referer=f"https://www.javbus.com/{code}")

    # Step 3: extract + deduplicate magnets
    seen = set()
    magnets = []
    for m in re.finditer(
        r'magnet:\?xt=urn:btih:([a-fA-F0-9]{40}|[A-Z2-7]{32,})(?:&dn=([^&\'\"\s\]]+))?', html
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
    try:
        data, elapsed = fetch_json(url, proxy=proxy)
        return data
    except Exception:
        return None


def _fetch_text(url: str, proxy: str = "", referer: str = "") -> str:
    headers = {}
    if referer:
        headers["Referer"] = referer
    try:
        status, body, elapsed = fetch(url, headers=headers, proxy=proxy or None)
        return body
    except Exception:
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
