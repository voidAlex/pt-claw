#!/usr/bin/env python3
"""
Query user profile info from PT sites (upload/download/ratio/bonus/seeding/level).

Usage:
    python3 site_profile.py                   # all sites
    python3 site_profile.py --site mteam      # single site
    python3 site_profile.py --json            # JSON output (default)
"""

import json, os, re, sys, time, urllib.request, urllib.error

from _common import _env, _fmt_size, _env_matching, _load_env_file, _parse_size
from _proxy import using_proxy
from mteam_api import _api_post
from pt_search import SITES, load_cookies


def _fetch_page(url, cookie, proxy=None, timeout=15):
    """GET a page with cookie auth, return decoded HTML or raise."""
    req = urllib.request.Request(url)
    req.add_header("Cookie", cookie)
    req.add_header("User-Agent",
                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0.0.0 Safari/537.36")
    with using_proxy(proxy):
        opener = urllib.request.build_opener()
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "")
            enc_match = re.search(r'charset=([\w-]+)', ct)
            encoding = enc_match.group(1) if enc_match else "utf-8"
            try:
                return raw.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                return raw.decode("utf-8", errors="replace")


def _extract_field(html, labels):
    """Find a value after any of the given label strings in HTML text."""
    for label in labels:
        # Pattern: label followed by optional HTML tags, then a value
        patterns = [
            # Label then value in next <td> or after colon/equals
            re.escape(label) + r'(?:</[^>]+>)?(?:\s*(?:<[^>]*>)+\s*)*\s*([\d,.]+\s*(?:TB|GB|MB|KB|B)\b|[\d,.]+)',
            re.escape(label) + r'(?:\s*[:：]\s*|\s*(?:<[^>]*>)+\s*)([\d,.]+\s*(?:TB|GB|MB|KB|B)\b|[\d,.]+)',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                return m.group(1).strip()
    return ""


def _extract_text_field(html, labels):
    """Find a text value after any of the given label strings."""
    for label in labels:
        # Match label followed by HTML tags and then text content
        pat = re.escape(label) + r'(?:\s*(?:<[^>]*>)+\s*|\s*[:：]\s*)([^<]{1,80})'
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _extract_ratio(html):
    """Extract share ratio — could be decimal like 2.78 or ∞/Inf."""
    labels = ["分享率", "Share ratio", "Ratio"]
    for label in labels:
        pat = re.escape(label) + r'(?:\s*(?:<[^>]*>)+\s*|\s*[:：]\s*)([\d.]+|∞|Inf)'
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val in ("∞", "Inf"):
                return float("inf")
            try:
                return float(val)
            except ValueError:
                pass
    return 0.0


def _parse_nexusphp_profile(site_id, site_cfg, cookie):
    """Scrape NexusPHP site profile via 3-phase scraping.

    Phase 1: GET /index.php — username, uploaded, downloaded, ratio, bonus, seeding, seeding_size
    Phase 2: GET /userdetails.php — level, join_time, is_donor, hnr_count, uploads
    Phase 3: GET /mybonus.php — bonus_per_hour, seeding_bonus
    """
    result = {"status": "ok"}
    base_url = site_cfg["url"].rstrip("/")
    proxy = _env("PT_PROXY") if site_cfg.get("needs_proxy") else None

    try:
        html = _fetch_page(f"{base_url}/index.php", cookie, proxy=proxy, timeout=15)
    except urllib.error.HTTPError as e:
        return {"status": "error", "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)[:120]}

    # Detect login page
    if "<title>" in html[:3000] and ("登录" in html[:3000] or "login" in html[:3000].lower()):
        return {"status": "error", "error": "Cookie expired"}

    # Try to find user info block — usually in a sidebar or top bar area
    # Narrow search to the info panel region if detectable
    info_html = html
    info_block = re.search(
        r'(?:class="[^"]*info_block|id="[^"]*info|class="[^"]*user[^"]*"|class="[^"]*status[^"]*").*?</table>',
        html, re.DOTALL | re.IGNORECASE)
    if info_block:
        info_html = info_block.group(0)

    # Also try to grab the right-side panel or specific stats sections
    # Many NexusPHP sites put stats in <td> blocks with specific width/layout
    # Fallback: search the full page

    # Username — look for common patterns
    username = _extract_text_field(html, ["用户名", "Username"])
    if not username:
        um = re.search(r'>([^<]{2,30})</a>\s*</(?:span|td|div)>(?:\s*<br)?', html)
        if um:
            username = um.group(1).strip()
    if username:
        result["username"] = username

    # Level / class
    level = _extract_text_field(html, ["等级", "Class", "User class", "用户等级", "级别"])
    if level:
        result["level"] = level

    # Uploaded
    uploaded_str = _extract_field(info_html, ["上传量", "上传", "Uploaded", "上传量："])
    if not uploaded_str:
        uploaded_str = _extract_field(html, ["上传量", "上传", "Uploaded"])
    if uploaded_str:
        result["uploaded"] = uploaded_str
        result["uploaded_bytes"] = _parse_size(uploaded_str)

    # Downloaded
    downloaded_str = _extract_field(info_html, ["下载量", "下载", "Downloaded", "下载量："])
    if not downloaded_str:
        downloaded_str = _extract_field(html, ["下载量", "下载", "Downloaded"])
    if downloaded_str:
        result["downloaded"] = downloaded_str
        result["downloaded_bytes"] = _parse_size(downloaded_str)

    # Ratio
    ratio = _extract_ratio(html)
    if ratio:
        result["ratio"] = ratio

    # Bonus / magic points
    bonus_str = _extract_field(info_html, ["魔力值", "魔力", "Bonus", "积分", "做种积分"])
    if not bonus_str:
        bonus_str = _extract_field(html, ["魔力值", "魔力", "Bonus", "积分"])
    if bonus_str:
        try:
            result["bonus"] = float(bonus_str.replace(",", ""))
        except ValueError:
            result["bonus"] = bonus_str

    # Seeding count
    seeding_str = _extract_field(info_html, ["做种数", "做种", "Seeding", "做种中"])
    if not seeding_str:
        seeding_str = _extract_field(html, ["做种数", "做种", "Seeding"])
    if seeding_str:
        try:
            result["seeding"] = int(float(seeding_str.replace(",", "")))
        except ValueError:
            pass

    # Seeding size
    seeding_size_str = _extract_field(info_html, ["做种量", "Seeding size", "做种体积"])
    if not seeding_size_str:
        seeding_size_str = _extract_field(html, ["做种量", "Seeding size", "做种体积"])
    if seeding_size_str:
        result["seeding_size"] = seeding_size_str

    # --- Phase 2: /userdetails.php — richer profile data ---
    try:
        detail_html = _fetch_page(f"{base_url}/userdetails.php", cookie, proxy=proxy, timeout=15)

        # Level — Phase 2 is more reliable than Phase 1 sidebar
        level2 = _extract_text_field(detail_html, ["等级", "Class", "User class", "用户等级"])
        if level2:
            result["level"] = level2

        # Join time
        join_time = _extract_text_field(detail_html, ["加入日期", "Join date"])
        if join_time:
            result["join_time"] = join_time

        # Donor — look for donor flag image
        is_donor = False
        if re.search(r'<img[^>]+alt\s*=\s*["\']Donor["\']', detail_html, re.IGNORECASE):
            is_donor = True
        elif re.search(r'<img[^>]+src\s*=\s*["\'][^"\']*flag[^"\']*["\']', detail_html, re.IGNORECASE):
            is_donor = True
        if is_donor:
            result["is_donor"] = True

        # H&R count — look for links to myhr.php with numbers like "2/5"
        hnr_match = re.search(r'href\s*=\s*["\'][^"\']*myhr\.php[^"\']*["\'][^>]*>\s*([\d]+)\s*/\s*([\d]+)', detail_html)
        if hnr_match:
            result["hnr_count"] = f"{hnr_match.group(1)}/{hnr_match.group(2)}"
        else:
            hnr_match2 = re.search(r'([\d]+)\s*/\s*([\d]+)[^<]*(?:<[^>]+>)*\s*(?:<a[^>]*myhr\.php)', detail_html)
            if hnr_match2:
                result["hnr_count"] = f"{hnr_match2.group(1)}/{hnr_match2.group(2)}"

        # Uploads — torrent upload count
        uploads_str = _extract_field(detail_html, ["发布", "上传种数", "Uploads"])
        if not uploads_str:
            uploads_str = _extract_text_field(detail_html, ["发布", "上传种数", "Uploads"])
        if uploads_str:
            result["uploads"] = uploads_str
    except Exception:
        pass

    # --- Phase 3: /mybonus.php — bonus rate info ---
    try:
        bonus_html = _fetch_page(f"{base_url}/mybonus.php", cookie, proxy=proxy, timeout=15)

        # Bonus per hour
        bph_match = re.search(
            r'(?:每小时|per hour|当前每小时能获取)(?:[^<\d]*?)([\d,.]+)',
            bonus_html, re.IGNORECASE)
        if bph_match:
            try:
                result["bonus_per_hour"] = float(bph_match.group(1).replace(",", ""))
            except ValueError:
                result["bonus_per_hour"] = bph_match.group(1)

        # Seeding bonus points
        sb_match = re.search(
            r'(?:做种积分|Seeding Points)(?:[^<\d]*?)([\d,.]+)',
            bonus_html, re.IGNORECASE)
        if sb_match:
            try:
                result["seeding_bonus"] = float(sb_match.group(1).replace(",", ""))
            except ValueError:
                result["seeding_bonus"] = sb_match.group(1)
    except Exception:
        pass

    # If we got nothing useful, mark as parse error
    has_data = any(k in result for k in ("uploaded", "downloaded", "ratio", "bonus", "seeding"))
    if not has_data:
        result["status"] = "error"
        result["error"] = "Could not parse profile data from page"

    return result


def _fetch_mteam_profile(api_key):
    """Query M-Team profile via API endpoints."""
    result = {"status": "ok"}

    # 1. Basic profile
    resp = _api_post("/member/profile", api_key)
    if str(resp.get("code")) != "0":
        return {"status": "error", "error": resp.get("message", "API error")[:120]}

    data = resp.get("data", {})
    member = data.get("member", {})
    member_count = data.get("memberCount", {})

    # Username
    username = member.get("username", "")
    if username:
        result["username"] = username

    # Level — from memberClass or memberGroup
    member_class = data.get("memberClass", {})
    member_group = data.get("memberGroup", {})
    level = ""
    if isinstance(member_class, dict):
        level = member_class.get("name", "")
    if not level and isinstance(member_group, dict):
        level = member_group.get("name", "")
    if level:
        result["level"] = level

    # Upload / Download
    uploaded_bytes = int(member_count.get("uploaded", 0))
    downloaded_bytes = int(member_count.get("downloaded", 0))

    result["uploaded_bytes"] = uploaded_bytes
    result["downloaded_bytes"] = downloaded_bytes
    result["uploaded"] = _fmt_size(uploaded_bytes) if uploaded_bytes else "0 B"
    result["downloaded"] = _fmt_size(downloaded_bytes) if downloaded_bytes else "0 B"

    # Ratio
    if downloaded_bytes > 0:
        result["ratio"] = round(uploaded_bytes / downloaded_bytes, 2)
    else:
        result["ratio"] = float("inf")

    # Bonus
    bonus = member_count.get("bonus", 0)
    try:
        result["bonus"] = float(bonus)
    except (TypeError, ValueError):
        result["bonus"] = 0

    # 2. Seeding statistics
    seed_resp = _api_post("/tracker/myPeerStatistics", api_key)
    if str(seed_resp.get("code")) == "0":
        seed_data = seed_resp.get("data", {})
        # Seeding count and total size
        seeding_count = int(seed_data.get("seeding", 0))
        seeding_size_bytes = int(seed_data.get("seedingSize", 0))
        if seeding_count:
            result["seeding"] = seeding_count
        if seeding_size_bytes:
            result["seeding_size"] = _fmt_size(seeding_size_bytes)
            result["seeding_size_bytes"] = seeding_size_bytes

    # 3. Unread messages
    msg_resp = _api_post("/msg/notify/statistic", api_key)
    if str(msg_resp.get("code")) == "0":
        msg_data = msg_resp.get("data", {})
        unread = int(msg_data.get("count", 0))
        result["unread_messages"] = unread

    # 4. Bonus rate (per-hour earnings, seeding bonus points)
    bonus_resp = _api_post("/tracker/mybonus", api_key)
    if str(bonus_resp.get("code")) == "0":
        bonus_data = bonus_resp.get("data", {})
        bph = bonus_data.get("bonusPerHour") or bonus_data.get("perHour")
        if bph is not None:
            try:
                result["bonus_per_hour"] = float(bph)
            except (TypeError, ValueError):
                result["bonus_per_hour"] = bph
        sb = bonus_data.get("seedingPoints") or bonus_data.get("seeding_bonus")
        if sb is not None:
            try:
                result["seeding_bonus"] = float(sb)
            except (TypeError, ValueError):
                result["seeding_bonus"] = sb

    return result


def _parse_ttg_profile(site_id, site_cfg, cookie):
    """Scrape TTG user profile from 3 pages (index + userdetails + mybonus)."""
    result = {"status": "ok"}
    base_url = site_cfg["url"].rstrip("/")
    proxy = _env("PT_PROXY") if site_cfg.get("needs_proxy") else None

    try:
        html = _fetch_page(f"{base_url}/index.php", cookie, proxy=proxy, timeout=15)
    except Exception as e:
        return {"status": "error", "error": str(e)[:120]}

    if "<title>" in html[:3000] and ("登录" in html[:3000] or "login" in html[:3000].lower()):
        return {"status": "error", "error": "Cookie expired"}

    username = _extract_text_field(html, ["用户名", "Username"])
    if username:
        result["username"] = username

    uploaded_str = _extract_field(html, ["上传量", "上传", "Uploaded"])
    if uploaded_str:
        result["uploaded"] = uploaded_str
        result["uploaded_bytes"] = _parse_size(uploaded_str)

    downloaded_str = _extract_field(html, ["下载量", "下载", "Downloaded"])
    if downloaded_str:
        result["downloaded"] = downloaded_str
        result["downloaded_bytes"] = _parse_size(downloaded_str)

    ratio = _extract_ratio(html)
    if ratio:
        result["ratio"] = ratio

    try:
        bonus_html = _fetch_page(f"{base_url}/mybonus.php", cookie, proxy=proxy, timeout=15)
        bonus_str = _extract_field(bonus_html, ["做种积分", "魔力值", "Bonus", "积分"])
        if bonus_str:
            try:
                result["bonus"] = float(bonus_str.replace(",", ""))
            except ValueError:
                result["bonus"] = bonus_str
    except Exception:
        pass

    has_data = any(k in result for k in ("uploaded", "downloaded", "ratio", "bonus"))
    if not has_data:
        result["status"] = "error"
        result["error"] = "Could not parse profile data from page"

    return result


def _fetch_site_profile(site_id, site_cfg, cookies):
    """Fetch profile for a single site. Returns result dict."""
    if site_id == "mteam":
        api_key = _env("MTEAM_API_KEY", "")
        if not api_key:
            return {"status": "error", "error": "MTEAM_API_KEY not set"}
        return _fetch_mteam_profile(api_key)

    cookie = cookies.get(site_id, "")
    if not cookie:
        return {"status": "error", "error": f"No cookie configured for {site_cfg['name']}"}

    if site_cfg.get("parser") == "nexusphp":
        return _parse_nexusphp_profile(site_id, site_cfg, cookie)

    if site_cfg.get("parser") == "ttg":
        return _parse_ttg_profile(site_id, site_cfg, cookie)

    return {"status": "error", "error": f"Unknown parser: {site_cfg.get('parser')}"}


def main():
    _load_env_file()

    args = sys.argv[1:]
    filter_site = None
    json_output = True

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--site" and i + 1 < len(args):
            filter_site = args[i + 1]
            i += 1
        elif arg == "--json":
            json_output = True
        elif arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        i += 1

    if filter_site and filter_site not in SITES:
        print(json.dumps({"error": f"Unknown site: {filter_site}. "
                                    f"Available: {', '.join(SITES.keys())}"}),
              file=sys.stderr)
        sys.exit(1)

    cookies = load_cookies()
    target_sites = {}
    if filter_site:
        target_sites[filter_site] = SITES[filter_site]
    else:
        target_sites = dict(SITES)

    profiles = {}
    for site_id, site_cfg in target_sites.items():
        profiles[site_id] = _fetch_site_profile(site_id, site_cfg, cookies)

    print(json.dumps(profiles, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
