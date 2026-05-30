#!/usr/bin/env python3
"""
Lightweight multi-PT-site search — zero services, direct HTTP.

Usage:
    python3 pt_search.py "流浪地球2"              # search all configured sites
    python3 pt_search.py "流浪地球2" --site 1ptba  # single site
    python3 pt_search.py "流浪地球2" --limit 10    # per-site limit

Config:
    Environment variables:
      PT_COOKIE_<SITE>  — cookie strings (one per site, from browser)
      MTEAM_API_KEY     — M-Team API key
      PT_PROXY          — proxy for sites that need it (auto-applied per site)
    This script's SITES dict    — site search URLs & parser type

Output: JSON array of results across all sites.
"""

import json, os, re, sys, time, urllib.request, urllib.parse, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.cookiejar import CookieJar

from _common import _load_env_file, _env, _fmt_size, _env_matching
from _proxy import using_proxy

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "secrets.env")

# NexusPHP promo CSS classes — aligned with PT-depiler NexusPHP.ts spstate enum
_PROMO_PATTERNS = [
    (r'class="[^"]*pro_free2up[^"]*"', "2xFree"),
    (r'class="[^"]*pro_2up[^"]*"', "2xUp"),
    (r'class="[^"]*pro_free[^"]*"', "Free"),
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


def _detect_promo(html_block: str) -> str:
    for pattern, label in _PROMO_PATTERNS:
        if re.search(pattern, html_block, re.IGNORECASE):
            return label
    return ""


# ── Site Registry ───────────────────────────────────────────
SITES = {
    "1ptba": {
        "name": "1PTBar",
        "url": "https://1ptba.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["综合", "影视"],
    },
    "btschool": {
        "name": "BTSCHOOL",
        "url": "https://pt.btschool.club",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合", "学习"],
    },
    "carpt": {
        "name": "CarPT",
        "url": "https://carpt.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "hdfans": {
        "name": "HDFans",
        "url": "https://hdfans.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["综合", "影视"],
    },
    "mteam": {
        "name": "M-Team",
        "url": "https://kp.m-team.cc",
        "api_host": "https://api.m-team.cc/api",
        "api_token": _env("MTEAM_API_KEY", ""),
        "parser": "mteam_api",
        "needs_proxy": True,
        "categories": ["影视", "综合", "成人"],
    },
    "pttime": {
        "name": "PTTime",
        "url": "https://www.pttime.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["影视", "综合", "成人"],
    },
    "soulvoice": {
        "name": "SoulVoice",
        "url": "https://pt.soulvoice.club",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合", "电子书", "有声书"],
    },
    "zmpt": {
        "name": "织梦",
        "url": "https://zmpt.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
}


def load_cookies() -> dict[str, str]:
    """Load cookie strings from environment variables (PT_COOKIE_<SITE>).
    Falls back to secrets.env if not in process environment."""
    cookies = {}
    for key, val in _env_matching("PT_COOKIE_").items():
        site_id = key[len("PT_COOKIE_"):].lower()
        cookies[site_id] = val
    return cookies


def search_site(site_id: str, site: dict, query: str, limit: int,
                timeout: int = 15, adult: bool = False) -> list[dict]:
    """Search a single PT site. Returns list of result dicts."""
    # API-based sites (no cookie/HTTP needed)
    if site.get("parser") == "mteam_api":
        return _search_mteam_api(site, query, limit, adult=adult)

    cookies = load_cookies()
    cookie_str = cookies.get(site_id, "")

    if not cookie_str:
        return [{"error": f"No cookie configured for {site['name']}",
                 "site": site["name"], "site_id": site_id}]

    if adult and site_id == "pttime":
        search_path = f"/adults.php?searchstr={urllib.parse.quote(query)}"
    else:
        search_path = site["search"].format(query=urllib.parse.quote(query))
    full_url = f"{site['url']}{search_path}"

    req = urllib.request.Request(full_url)
    req.add_header("Cookie", cookie_str)
    req.add_header("User-Agent",
                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0.0.0 Safari/537.36")

    proxy = _env("PT_PROXY") if site.get("needs_proxy") else None
    try:
        with using_proxy(proxy):
            opener = urllib.request.build_opener()
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                match = re.search(r'charset=([\w-]+)', content_type)
                encoding = match.group(1) if match else "utf-8"
                try:
                    html = raw.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    html = raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return [{"error": f"HTTP {e.code}", "site": site["name"],
                 "site_id": site_id}]
    except Exception as e:
        return [{"error": str(e), "site": site["name"], "site_id": site_id}]

    # Detect if we got a login page instead of results
    if "<title>" in html and "登录" in html[:2000]:
        return [{"error": "Cookie expired — re-login needed",
                 "site": site["name"], "site_id": site_id}]

    # Parse
    if site["parser"] == "nexusphp":
        results = _parse_nexusphp(html, site, site_id, limit)
        if not results or ("error" in (results[0] if results else {})):
            results = _parse_nexusphp_classic(html, site, site_id, limit)
        return results
    elif site["parser"] == "mteam_api":
        return _search_mteam_api(site, query, limit, adult=adult)


def _parse_nexusphp_classic(html: str, site: dict, site_id: str,
                           limit: int) -> list[dict]:
    """Parse classic NexusPHP — same structure as PTTime but no data= attr.

    Each torrent: title <tr> + stats cells between that </tr> and next <tr.
    """
    results = []
    seen_ids = set()

    # Find all download links
    dl_matches = list(re.finditer(
        r'href="(download\.php\?id=(\d+)[^"]*)"', html))

    for dl_match in dl_matches:
        dl_url = dl_match.group(1)
        tid = dl_match.group(2)
        if tid in seen_ids:
            continue
        seen_ids.add(tid)

        # Find enclosing <tr> — the title row
        before = html[:dl_match.start()]
        tr_start = before.rfind('<tr')
        if tr_start == -1:
            continue

        # Find the title row's closing </tr> (handle nested <tr>)
        after_tr = html[tr_start:]
        depth = 0
        tr_close = 0
        for m in re.finditer(r'<(/?tr)\b', after_tr):
            if m.group(1) == 'tr':
                depth += 1
            else:
                if depth == 1:
                    tr_close = tr_start + m.end()
                    break
                depth -= 1

        title_html = html[tr_start:tr_close]

        # Stats: cells between title row's </tr> and next <tr> or </tbody>
        after_title = html[tr_close:]
        next_tr = re.search(r'<(?:tr\b|/tbody)', after_title)
        stats_end = tr_close + next_tr.start() if next_tr else tr_close + len(after_title)
        stats_html = html[tr_close:stats_end]

        # Title
        title = ""
        tm = re.search(r'<a[^>]*title="([^"]+)"[^>]*>', title_html)
        if tm:
            title = tm.group(1).strip()
        if not title or len(title) < 4:
            tm = re.search(
                r'href="details\.php\?id=' + tid + r'[^"]*"[^>]*>(.*?)</a>',
                title_html, re.DOTALL)
            if tm:
                title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
        if not title:
            continue

        # Size from stats cells
        size_str = ""
        sm = re.search(
            r'>\s*([\d.,]+)\s*(?:<br\s*/?>\s*)?(GB|MB|TB|KB)\s*<',
            stats_html, re.IGNORECASE)
        if sm:
            size_str = f"{sm.group(1)} {sm.group(2).upper()}"

        # Seeds: <b>N</b> in stats cells, first matches are seeders/leechers
        seeds = 0
        leech = 0
        seed_m = re.search(r'seeders[^>]*>\s*<b>(\d+)</b>', stats_html)
        if seed_m:
            seeds = int(seed_m.group(1))
        leech_m = re.search(r'leechers[^>]*>\s*<b>(\d+)</b>', stats_html)
        if leech_m:
            leech = int(leech_m.group(1))
        if seeds == 0:
            bolds = re.findall(r'<b>(\d+)</b>', stats_html)
            seeds = int(bolds[0]) if bolds else 0
            leech = int(bolds[1]) if len(bolds) > 1 else 0

        promo = _detect_promo(title_html + stats_html)

        results.append({
            "title": title.strip(),
            "size": size_str, "size_bytes": 0,
            "seeders": seeds, "leechers": leech,
            "category": "", "promo": promo,
            "download_url": site["url"] + "/" + dl_url,
            "site": site["name"], "site_id": site_id,
            "source": site_id,
        })
        if len(results) >= limit:
            break

    if not results:
        return [{"error": "No results found", "site": site["name"], "site_id": site_id}]
    results.sort(key=lambda r: r["seeders"], reverse=True)
    return results[:limit]


def _search_mteam_api(site: dict, query: str, limit: int, adult: bool = False) -> list[dict]:
    """Search M-Team via REST API. Delegates to mteam_api module."""
    api_token = site.get("api_token", "")
    if not api_token:
        return [{"error": "No API token configured",
                 "site": site["name"], "site_id": "mteam"}]

    proxy = _env("PT_PROXY")
    if not proxy:
        return [{"error": "PT_PROXY not set — M-Team API requires proxy",
                 "site": site["name"], "site_id": "mteam"}]

    from mteam_api import search as mteam_search, get_download_url as mteam_dl_url

    items = mteam_search(query, api_token, limit=limit, adult=adult)

    if not items:
        return [{"error": "No results found", "site": site["name"],
                 "site_id": "mteam"}]
    if len(items) == 1 and "error" in items[0]:
        items[0]["site"] = site["name"]
        items[0]["site_id"] = "mteam"
        return items

    results = []
    for item in items:
        if "error" in item:
            continue
        dl_url = ""
        torrent_id = item.get("id", "")
        if torrent_id:
            dl_url = mteam_dl_url(torrent_id, api_token)
        results.append({
            "title": item.get("title", "").strip(),
            "detail_url": item.get("detail_url", ""),
            "download_url": dl_url,
            "size": item.get("size", ""),
            "size_bytes": item.get("size_bytes", 0),
            "seeders": item.get("seeders", 0),
            "leechers": item.get("leechers", 0),
            "category": item.get("category", ""),
            "promo": item.get("promo", ""),
            "site": site["name"],
            "site_id": "mteam",
            "source": "mteam",
        })

    if not results:
        return [{"error": "No results found", "site": site["name"],
                 "site_id": "mteam"}]

    results.sort(key=lambda r: r["seeders"], reverse=True)
    return results[:limit]


def _parse_nexusphp(html: str, site: dict, site_id: str,
                    limit: int) -> list[dict]:
    """Parse NexusPHP/PTTime torrent listing.

    Structure: each torrent spans from one <tr data=ID> to the next.
    Title in <tr data=ID>, stats (size, seeds) in cells between the
    title row closing and the next <tr data=ID>.
    """
    results = []

    # Find all <tr data=TID> start positions
    title_starts = [(m.start(), m.group(1), m.group(2))
                    for m in re.finditer(
                        r'<tr\s+data=(\d+)\b[^>]*>(.*?)</tr>',
                        html, re.DOTALL)]

    for idx, (start, torrent_id, title_html) in enumerate(title_starts):
        # The stats block is from the title row's closing </tr>
        # to the next <tr data=...> start (or end of HTML)
        title_row_end = start + len(re.search(
            r'<tr\s+data=' + torrent_id + r'\b[^>]*>.*?</tr>',
            html[start:], re.DOTALL).group(0))
        
        if idx + 1 < len(title_starts):
            stats_end = title_starts[idx + 1][0]
        else:
            # Last torrent — find next major section boundary
            stats_end = min(len(html), title_row_end + 5000)

        stats_html = html[title_row_end:stats_end]

        # Parse title
        title = ""
        tm = re.search(r'<a[^>]*title="([^"]+)"[^>]*>(.*?)</a>',
                       title_html, re.DOTALL)
        if tm:
            title = tm.group(1).strip()
            if len(title) < 5:
                title = re.sub(r'<[^>]+>', '', tm.group(2)).strip()
        if not title:
            tm = re.search(r'<a[^>]*>(.*?)</a>', title_html, re.DOTALL)
            if tm:
                title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
        if not title:
            continue

        # Parse stats
        size_str = ""
        size_bytes = 0
        sm = re.search(
            r'>\s*([\d.,]+)\s*(?:<br\s*/?>\s*)?(GB|MB|TB|KB|B)\s*<',
            stats_html, re.IGNORECASE)
        if sm:
            size_str = f"{sm.group(1)} {sm.group(2).upper()}"
            try:
                sz = float(sm.group(1).replace(",", ""))
                unit = sm.group(2).upper()
                mult = {"B": 1, "KB": 1024, "MB": 1048576,
                        "GB": 1073741824, "TB": 1099511627776}
                size_bytes = int(sz * mult.get(unit, 1))
            except ValueError:
                pass

        # Seeds: <b>N</b> in stats area. First <b> is almost always seeders.
        bolds = re.findall(r'<b>(\d+)</b>', stats_html)
        seeders = int(bolds[0]) if bolds else 0
        leechers = int(bolds[1]) if len(bolds) > 1 else 0

        promo = _detect_promo(title_html + stats_html)

        cat = re.search(r'<span[^>]*title="([^"]*)"', title_html)
        category = cat.group(1) if cat else ""

        dl = re.search(r'download\.php\?id=' + torrent_id + r'[^"\'\s]*', html)
        dl_url = (site["url"] + "/" + dl.group(0)) if dl else ""

        results.append({
            "title": title.strip(),
            "size": size_str,
            "size_bytes": size_bytes,
            "seeders": seeders,
            "leechers": leechers,
            "category": category,
            "promo": promo,
            "download_url": dl_url,
            "site": site["name"],
            "site_id": site_id,
            "source": site_id,
        })

        if len(results) >= limit:
            break

    if not results:
        return [{"error": "No results found", "site": site["name"],
                 "site_id": site_id}]

    results.sort(key=lambda r: r["seeders"], reverse=True)
    return results[:limit]


def main():
    raw_args = sys.argv[1:]

    if "--help" in raw_args or "-h" in raw_args:
        print(__doc__)
        sys.exit(0)

    # Parse named flags
    flags = {}
    positional = []
    skip_next = False
    for i, a in enumerate(raw_args):
        if skip_next:
            skip_next = False
            continue
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(raw_args) and not raw_args[i + 1].startswith("--"):
                flags[key] = raw_args[i + 1]
                skip_next = True
            else:
                flags[key] = True
        else:
            positional.append(a)

    query = " ".join(positional)
    if not query:
        print(json.dumps({"error": "No search query provided"}))
        sys.exit(1)

    # Which sites to search
    target_sites = {}
    if "site" in flags:
        site_id = flags["site"]
        if site_id in SITES:
            target_sites[site_id] = SITES[site_id]
        else:
            print(json.dumps({"error": f"Unknown site: {site_id}"}))
            sys.exit(1)
    else:
        target_sites = {k: v for k, v in SITES.items()}

    # Limit
    limit = int(flags.get("limit", 20))
    adult = flags.get("adult", False)
    actor = flags.get("actor", "")

    if adult and actor and "pttime" in target_sites:
        s = target_sites["pttime"]
        search_path = f"/adults.php?actor={urllib.parse.quote(actor)}"
        full_url = f"{s['url']}{search_path}"
        cookies = load_cookies()
        cookie_str = cookies.get("pttime", "")
        if not cookie_str:
            print(json.dumps({"error": "No cookie configured for PTTime"}))
            sys.exit(1)
        req = urllib.request.Request(full_url)
        req.add_header("Cookie", cookie_str)
        req.add_header("User-Agent",
                       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0.0.0 Safari/537.36")
        proxy = _env("PT_PROXY") if s.get("needs_proxy") else None
        with using_proxy(proxy):
            opener = urllib.request.build_opener()
            try:
                with opener.open(req, timeout=15) as resp:
                    raw = resp.read()
                    ct = resp.headers.get("Content-Type", "")
                    m = re.search(r'charset=([\w-]+)', ct)
                    enc = m.group(1) if m else "utf-8"
                    try:
                        html = raw.decode(enc)
                    except (UnicodeDecodeError, LookupError):
                        html = raw.decode("utf-8", errors="replace")
            except Exception as e:
                print(json.dumps({"error": str(e), "site": "PTTime"}))
                sys.exit(1)
        results = _parse_nexusphp(html, s, "pttime", limit)
        if not results or ("error" in (results[0] if results else {})):
            results = _parse_nexusphp_classic(html, s, "pttime", limit)
        print(json.dumps({"query": f"actor:{actor}", "total": len(results),
                          "results": results}, ensure_ascii=False, indent=2))
        return

    # Search all sites
    all_results = []
    errors = []

    if len(target_sites) == 1:
        # Single site — no thread pool overhead
        sid, site = next(iter(target_sites.items()))
        for item in search_site(sid, site, query, limit, adult=adult):
            if "error" in item:
                errors.append(item)
            else:
                all_results.append(item)
    else:
        # Multi-site parallel
        with ThreadPoolExecutor(max_workers=min(len(target_sites), 5)) as executor:
            futures = {
                executor.submit(search_site, sid, site, query, limit, adult=adult): sid
                for sid, site in target_sites.items()
            }
            for future in as_completed(futures):
                sid = futures[future]
                try:
                    r = future.result()
                    for item in r:
                        if "error" in item:
                            errors.append(item)
                        else:
                            all_results.append(item)
                except Exception as e:
                    errors.append({"error": str(e), "site": SITES[sid]["name"],
                                   "site_id": sid})

    # Sort all results by seeders descending
    all_results.sort(key=lambda r: r.get("seeders", 0), reverse=True)

    output = {
        "query": query,
        "total": len(all_results),
        "errors": errors,
        "results": all_results,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
