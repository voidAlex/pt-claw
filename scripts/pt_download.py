#!/usr/bin/env python3
"""
Download from PT site detail page URL — extract download link, fetch .torrent, push to qB.

Works for ALL NexusPHP sites (115+) and M-Team (API).

Usage:
    python3 pt_download.py "https://pt.btschool.club/details.php?id=172580"
    python3 pt_download.py "https://pt.btschool.club/details.php?id=172580" --tags btschool
    python3 pt_download.py "https://kp.m-team.cc/detail/12345" --category "电影" --tags mteam
    python3 pt_download.py url1 url2 url3 --tags batch --category "电影"

    # Dry run — show info without downloading
    python3 pt_download.py "https://pt.btschool.club/details.php?id=172580" --check

    # Re-download to a specific save path
    python3 pt_download.py "https://pt.btschool.club/details.php?id=172580" --save-path /media/downloads

How it works:
    1. Parse detail page URL → detect site (by domain) + torrent ID
    2. Fetch detail page HTML → extract title and promo info
    3. Build download URL:
       - NexusPHP: <site_url>/download.php?id=<torrent_id>
       - M-Team: API genDlToken → signed download URL
    4. Fetch .torrent binary with site cookie
    5. Upload .torrent to qBittorrent via multipart form + apply tags/category
"""
import json, os, re, sys, urllib.parse

from _common import _env, _env_matching, _is_login_page
from _http import fetch, fetch_raw
from _logger import get_logger

log = get_logger("pt_download")

_skill_dir = os.path.dirname(os.path.abspath(__file__))


def _match_site(detail_url: str) -> tuple[str, dict] | None:
    """Match a detail page URL to a site in the SITES registry by domain."""
    sys.path.insert(0, _skill_dir)
    from pt_search import SITES

    parsed = urllib.parse.urlparse(detail_url)
    domain = parsed.hostname or ""
    domain_lower = domain.lower().lstrip("www.")

    for site_id, site_cfg in SITES.items():
        site_parsed = urllib.parse.urlparse(site_cfg["url"])
        site_domain = site_parsed.hostname or ""
        site_domain_lower = site_domain.lower().lstrip("www.")
        if domain_lower == site_domain_lower or domain_lower.endswith("." + site_domain_lower):
            return site_id, site_cfg

    return None


def _extract_torrent_id(detail_url: str, site_id: str, site_cfg: dict) -> str | None:
    """Extract torrent ID from detail page URL.

    NexusPHP: details.php?id=12345
    M-Team:   detail/12345
    """
    parsed = urllib.parse.urlparse(detail_url)
    path = parsed.path
    qs = urllib.parse.parse_qs(parsed.query)

    if "id" in qs:
        return qs["id"][0]

    m = re.search(r'/details?\.php.*[?&]id=(\d+)', detail_url, re.IGNORECASE)
    if m:
        return m.group(1)

    m = re.search(r'/detail/(\d+)', path)
    if m:
        return m.group(1)

    return None


def _fetch_detail_info(detail_url: str, site_id: str, site_cfg: dict) -> dict:
    """Fetch detail page HTML and extract title + promo info."""
    cookie_str = _get_cookie(site_id)
    proxy = _env("PT_PROXY") if site_cfg.get("needs_proxy") else None
    headers = {}
    if cookie_str:
        headers["Cookie"] = cookie_str

    status, html, elapsed = fetch(
        detail_url, headers=headers, proxy=proxy,
        warmup=(proxy is not None), timeout=20,
    )

    if status != 200:
        return {"error": f"HTTP {status} fetching detail page", "site_id": site_id}

    if _is_login_page(html):
        return {"error": "Cookie expired — re-login needed", "site_id": site_id}

    title = _extract_title(html)
    promo = _detect_promo(html)
    size_str = _extract_size(html)

    return {
        "title": title,
        "promo": promo,
        "size": size_str,
        "site_id": site_id,
        "site_name": site_cfg["name"],
    }


def _get_cookie(site_id: str) -> str:
    cookies = {}
    for key, val in _env_matching("PT_COOKIE_").items():
        sid = key[len("PT_COOKIE_"):].lower()
        cookies[sid] = val
    return cookies.get(site_id, "")


def _extract_title(html: str) -> str:
    # NexusPHP detail pages: <h1 class="torrent-title"> or <h1> enclosing torrent name
    h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
    if h1:
        text = re.sub(r'<[^>]+>', '', h1.group(1)).strip()
        if len(text) > 3:
            return text

    # Try the <title> tag but strip site prefix ("SITENAME :: 种子详情 "..."")
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if m:
        title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        # Extract quoted part: SITENAME :: 种子详情 "Actual Title" ...
        qm = re.search(r'["""](.+?)["""]', title)
        if qm:
            return qm.group(1)
        # Strip common prefix: "SITENAME :: 种子详情 "
        for sep in [" :: ", " - ", " — "]:
            if sep in title:
                after = title.split(sep, 1)[1].strip()
                if len(after) > 5:
                    return after

    return ""


_PROMO_PATTERNS = [
    (r'class="[^"]*pro_free2up[^"]*"', "2xFree"),
    (r'class="[^"]*pro_50pctdown2up[^"]*"', "2x50%"),
    (r'class="[^"]*pro_2up[^"]*"', "2xUp"),
    (r'class="[^"]*pro_free[^"]*"', "Free"),
    (r'class="[^"]*pro_50pctdown[^"]*"', "50%"),
    (r'class="[^"]*pro_30pctdown[^"]*"', "30%"),
    (r'class="[^"]*pro_halfdown[^"]*"', "50%"),
    (r'class="[^"]*pro_30percent[^"]*"', "30%"),
    (r'class="[^"]*pro_custom[^"]*"', "Custom"),
    (r'class="[^"]*free[^"]*".*class="[^"]*twoup[^"]*"', "2xFree"),
    (r'class="[^"]*twoup[^"]*"', "2xUp"),
    (r'class="[^"]*(?:^|\s)(?:free|_free)(?:\s|")[^"]*"', "Free"),
    (r'>\s*Free\s*<', "Free"),
    (r'>\s*2\s*x\s*Free\s*<', "2xFree"),
    (r'>\s*50\s*%\s*<', "50%"),
    (r'>\s*30\s*%\s*<', "30%"),
]


def _detect_promo(html: str) -> str:
    for pattern, label in _PROMO_PATTERNS:
        if re.search(pattern, html, re.IGNORECASE):
            return label
    return ""


def _extract_size(html: str) -> str:
    m = re.search(r'(?i)(?:大\s*小|size|文件大小)[^\d<>]*?([\d.,]+\s*(?:TB|GB|MB|KB))', html)
    if m:
        return m.group(1).strip()
    return ""


def _build_download_url(site_id: str, site_cfg: dict, torrent_id: str) -> str | None:
    if site_cfg.get("parser") == "mteam_api":
        from mteam_api import get_download_url
        api_key = _env("MTEAM_API_KEY", "")
        if not api_key:
            raise RuntimeError("MTEAM_API_KEY not set for M-Team download")
        return get_download_url(torrent_id, api_key)

    return f"{site_cfg['url']}/download.php?id={torrent_id}"


def _fetch_torrent_binary(download_url: str, site_id: str, site_cfg: dict) -> bytes:
    if site_cfg.get("parser") == "mteam_api":
        proxy = _env("PT_PROXY")
        if not proxy:
            raise RuntimeError("PT_PROXY not set — M-Team requires proxy")
        status, raw, elapsed = fetch_raw(
            download_url,
            headers={"User-Agent": "Mozilla/5.0"},
            proxy=proxy, warmup=True, timeout=30,
        )
    else:
        cookie_str = _get_cookie(site_id)
        proxy = _env("PT_PROXY") if site_cfg.get("needs_proxy") else None
        headers = {}
        if cookie_str:
            headers["Cookie"] = cookie_str
        status, raw, elapsed = fetch_raw(
            download_url, headers=headers, proxy=proxy,
            warmup=(proxy is not None), timeout=30,
        )

    if status != 200:
        raise RuntimeError(f"HTTP {status} downloading .torrent from {site_cfg['name']}")

    if len(raw) < 50 or not raw.startswith(b"d"):
        raise RuntimeError(
            f"Invalid .torrent response ({len(raw)} bytes) — "
            f"cookie may be expired or download access denied"
        )

    log.info("fetched .torrent site=%s size=%d bytes", site_id, len(raw))
    return raw


def _upload_to_qb(torrent_data: bytes, torrent_id: str, site_id: str,
                  save_path: str = None, category: str = None,
                  tags: list[str] = None) -> dict:
    from _qb_session import get_session

    opener, qb_url = get_session()
    boundary = f"----PtClaw{torrent_id}"
    filename = f"{site_id}_{torrent_id}.torrent"

    parts = []
    parts.append(f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="torrents"; '
                 f'filename="{filename}"\r\n'
                 f"Content-Type: application/x-bittorrent\r\n\r\n".encode())

    field_parts = []
    if save_path:
        field_parts.append(f'--{boundary}\r\n'
                           f'Content-Disposition: form-data; name="savepath"\r\n\r\n'
                           f'{save_path}\r\n')
    if category:
        field_parts.append(f'--{boundary}\r\n'
                           f'Content-Disposition: form-data; name="category"\r\n\r\n'
                           f'{category}\r\n')
    if tags:
        tag_str = ",".join(tags)
        field_parts.append(f'--{boundary}\r\n'
                           f'Content-Disposition: form-data; name="tags"\r\n\r\n'
                           f'{tag_str}\r\n')

    body = b"".join(parts) + torrent_data + b"\r\n"
    for fp in field_parts:
        body += fp.encode()
    body += f"--{boundary}--\r\n".encode()

    import urllib.request
    req = urllib.request.Request(
        f"{qb_url}/api/v2/torrents/add",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with opener.open(req, timeout=30) as resp:
            resp_data = resp.read()
        log.info("qB upload ok site=%s torrent_id=%s", site_id, torrent_id)
        return {"success": True}
    except Exception as e:
        log.error("qB upload failed site=%s torrent_id=%s error=%s", site_id, torrent_id, e)
        return {"error": f"qB upload failed: {e}"}


def download_from_url(detail_url: str, save_path: str = None,
                      category: str = None, tags: list[str] = None,
                      dry_run: bool = False) -> dict:
    """Main entry: detail page URL → download .torrent → push to qB."""
    match = _match_site(detail_url)
    if not match:
        return {"error": f"URL domain not recognized in SITES registry: {detail_url}"}
    site_id, site_cfg = match

    torrent_id = _extract_torrent_id(detail_url, site_id, site_cfg)
    if not torrent_id:
        return {"error": f"Cannot extract torrent ID from URL: {detail_url}"}

    log.info("matched site=%s torrent_id=%s url=%s", site_id, torrent_id, detail_url)

    info = _fetch_detail_info(detail_url, site_id, site_cfg)
    if "error" in info:
        return info

    if dry_run:
        return {
            "dry_run": True,
            "site_id": site_id,
            "site_name": site_cfg["name"],
            "torrent_id": torrent_id,
            "title": info.get("title", ""),
            "promo": info.get("promo", ""),
            "size": info.get("size", ""),
            "download_url": f"{site_cfg['url']}/download.php?id={torrent_id}"
            if site_cfg.get("parser") != "mteam_api" else "(API genDlToken)",
        }

    download_url = _build_download_url(site_id, site_cfg, torrent_id)
    if not download_url:
        return {"error": f"Failed to build download URL for {site_id}/{torrent_id}"}

    try:
        torrent_data = _fetch_torrent_binary(download_url, site_id, site_cfg)
    except Exception as e:
        log.error("fetch .torrent failed site=%s id=%s error=%s", site_id, torrent_id, e)
        return {"error": str(e)}

    upload_result = _upload_to_qb(
        torrent_data, torrent_id, site_id,
        save_path=save_path, category=category, tags=tags or [site_id],
    )
    if "error" in upload_result:
        return upload_result

    return {
        "success": True,
        "site_id": site_id,
        "site_name": site_cfg["name"],
        "torrent_id": torrent_id,
        "title": info.get("title", ""),
        "promo": info.get("promo", ""),
        "size": info.get("size", ""),
        "download_url": download_url,
        "torrent_size_bytes": len(torrent_data),
        "tags": tags or [site_id],
    }


def _parse_args(argv: list[str]) -> dict:
    urls = []
    flags = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--tags", "--tag"):
            i += 1; flags["tags"] = [t.strip() for t in argv[i].split(",")] if i < len(argv) else []
        elif a == "--category":
            i += 1; flags["category"] = argv[i] if i < len(argv) else ""
        elif a == "--save-path":
            i += 1; flags["save_path"] = argv[i] if i < len(argv) else ""
        elif a in ("--check", "--dry-run"):
            flags["dry_run"] = True
        elif a.startswith("http"):
            urls.append(a)
        else:
            pass
        i += 1
    flags["urls"] = urls
    return flags


def main():
    parsed = _parse_args(sys.argv[1:])
    urls = parsed.get("urls", [])

    if not urls:
        print(json.dumps({"error": "No URLs provided. Usage: pt_download.py <detail_url> [--tags t1,t2] [--category cat] [--save-path path] [--check]"}))
        sys.exit(1)

    results = []
    for url in urls:
        result = download_from_url(
            url,
            save_path=parsed.get("save_path"),
            category=parsed.get("category"),
            tags=parsed.get("tags"),
            dry_run=parsed.get("dry_run", False),
        )
        results.append(result)

    if len(results) == 1:
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
