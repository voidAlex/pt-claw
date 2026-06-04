#!/usr/bin/env python3
"""
Query user profile info from PT sites (upload/download/ratio/bonus/seeding/level).

Usage:
    python3 site_profile.py                   # configured sites only (have cookies/api-key)
    python3 site_profile.py --site mteam      # single site
    python3 site_profile.py --json            # JSON output (default)
    python3 site_profile.py --all             # query all 115 sites (original behavior)
    python3 site_profile.py --debug           # include raw HTML excerpts for NexusPHP parsing diagnosis
"""

import json, os, re, sys, time

from _common import _env, _fmt_size, _env_matching, _load_env_file, _parse_size, _is_login_page
from _http import fetch
from _logger import get_logger
from mteam_api import _api_post
from pt_search import SITES, load_cookies

log = get_logger("site_profile")


def _fetch_page(url, cookie, proxy=None, timeout=15):
    """GET a page with cookie auth, return decoded HTML or raise."""
    status, html, elapsed = fetch(
        url, headers={"Cookie": cookie}, proxy=proxy,
        warmup=(proxy is not None), timeout=timeout,
    )
    return html


def _extract_field(html, labels):
    """Find a value after any of the given label strings in HTML text."""
    for label in labels:
        # Pattern: label followed by optional HTML tags, then a value
        # Use word boundaries to avoid matching inside HTML attributes
        patterns = [
            # Label then value in next <td> or after colon/equals
            r'\b' + re.escape(label) + r'\b' + r'(?:</[^>]+>)?(?:\s*(?:<[^>]*>)+\s*)*\s*([\d,.]+\s*(?:TB|GB|MB|KB|B)\b|[\d,.]+)',
            r'\b' + re.escape(label) + r'\b' + r'(?:\s*[:：]\s*|\s*(?:<[^>]*>)+\s*)\s*([\d,.]+\s*(?:TB|GB|MB|KB|B)\b|[\d,.]+)',
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


def _extract_table_cells(html):
    """Parse HTML into a list of (label_text, value_cell_dict) pairs from table rows.

    For each <tr>, find all <td> cells. Pairs are formed:
    - If a cell contains label-like text (short, non-empty), the NEXT cell is its value
    - This mimics CSS selector: td.rowhead:contains('label') + td

    Each value_cell_dict has keys: 'text' (stripped text) and 'html' (raw inner HTML).

    Returns list of (label, value_dict) tuples.
    """
    pairs = []
    for tr_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE):
        row_html = tr_match.group(1)
        # Skip rows that are inside nested tables — simplified check
        if row_html.count('<tr') > 0:
            continue
        cells = []
        for td_match in re.finditer(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE):
            cell_html = td_match.group(1)
            cell_text = re.sub(r'<[^>]+>', '', cell_html).strip()
            cells.append({'text': cell_text, 'html': cell_html})

        for i in range(len(cells) - 1):
            text = cells[i]['text']
            if text and len(text) < 50:
                pairs.append((text, cells[i + 1]))

    return pairs


def _find_cell_value(pairs, labels, default=""):
    """Find the first matching label in table cell pairs and return its value text."""
    for label in labels:
        for pair_label, pair_value in pairs:
            if label in pair_label:
                return pair_value['text']
    return default


def _find_cell_html(pairs, labels):
    """Find matching label and return the raw HTML of the value cell (for img title extraction)."""
    for label in labels:
        for pair_label, pair_value in pairs:
            if label in pair_label:
                return pair_value['html']
    return ""


def _parse_nexusphp_profile(site_id, site_cfg, cookie, debug=False):
    """Scrape NexusPHP site profile via 3-phase scraping.

    Phase 1: GET /index.php — username, uploaded, downloaded, ratio, bonus, seeding, seeding_size
    Phase 2: GET /userdetails.php — level, join_time, is_donor, hnr_count, uploads
    Phase 3: GET /mybonus.php — bonus_per_hour, seeding_bonus
    """
    result = {"status": "ok"}
    base_url = site_cfg["url"].rstrip("/")
    proxy = _env("PT_PROXY") if site_cfg.get("needs_proxy") else None

    debug_info = None
    if debug:
        debug_info = {"matched_labels": {}, "table_cells_found": 0}

    try:
        html = _fetch_page(f"{base_url}/index.php", cookie, proxy=proxy, timeout=15)
    except Exception as e:
        return {"status": "error", "error": str(e)[:120]}

    if _is_login_page(html):
        return {"status": "error", "error": "Cookie expired"}

    if debug:
        title_m = re.search(r'<title>([^<]*)</title>', html, re.IGNORECASE)
        debug_info["page_title"] = title_m.group(1).strip() if title_m else ""

    # === Table-row-based extraction (primary) ===
    pairs = _extract_table_cells(html)
    if debug:
        debug_info["table_cells_found"] = len(pairs)
        debug_info["table_pairs_sample"] = [
            (lbl, val['text'][:80]) for lbl, val in pairs[:20]
        ]

    username = _find_cell_value(pairs, ["用户名", "Username"])
    if not username:
        username = _extract_text_field(html, ["用户名", "Username"])
    if not username:
        um = re.search(r'>([^<]{2,30})</a>\s*</(?:span|td|div)>(?:\s*<br)?', html)
        if um:
            username = um.group(1).strip()
    if username:
        result["username"] = username
    if debug:
        debug_info["matched_labels"]["username"] = username or ""

    level = _find_cell_value(pairs, ["等级", "等級", "Class", "User class", "用户等级", "级别"])
    if not level:
        level = _extract_text_field(html, ["等级", "Class", "User class", "用户等级", "级别"])
    if level:
        result["level"] = level
    if debug:
        debug_info["matched_labels"]["level_phase1"] = level or ""

    # Uploaded / Downloaded — often BOTH in the same "传输" cell
    # e.g. cell text: "上传量: 5.36 TB  下载量: 2.18 TB"
    transfer_labels = ["传输", "傳送", "Transfers", "流量", "数据统计"]
    transfer_cell_text = _find_cell_value(pairs, transfer_labels)

    uploaded_str = ""
    downloaded_str = ""

    if transfer_cell_text:
        up_m = re.search(
            r'(?:上[传傳]量|Uploaded)\s*[:：]?\s*([\d,.\s]+(?:TB|GB|MB|KB|B))',
            transfer_cell_text, re.IGNORECASE)
        if up_m:
            uploaded_str = up_m.group(1).strip()
        dn_m = re.search(
            r'(?:下[载載]量|Downloaded)\s*[:：]?\s*([\d,.\s]+(?:TB|GB|MB|KB|B))',
            transfer_cell_text, re.IGNORECASE)
        if dn_m:
            downloaded_str = dn_m.group(1).strip()

    if not uploaded_str:
        uploaded_str = _find_cell_value(pairs, ["上传量", "上傳量", "Uploaded"])
    if not downloaded_str:
        downloaded_str = _find_cell_value(pairs, ["下载量", "下載量", "Downloaded"])

    if not uploaded_str:
        uploaded_str = _extract_field(html, ["上传量", "上传", "Uploaded", "上传量："])
    if not downloaded_str:
        downloaded_str = _extract_field(html, ["下载量", "下载", "Downloaded", "下载量："])

    if not uploaded_str:
        up_m2 = re.search(
            r'[^总]上[传傳]量?[:：_<>/a-zA-Z\-="\s#;]+([\d,.\s]+[KMGTPI]*B)',
            html, re.IGNORECASE)
        if up_m2:
            uploaded_str = up_m2.group(1).strip()
    if not downloaded_str:
        dn_m2 = re.search(
            r'[^总子影力]下[载載]量?[:：_<>/a-zA-Z\-="\s#;]+([\d,.\s]+[KMGTPI]*B)',
            html, re.IGNORECASE)
        if dn_m2:
            downloaded_str = dn_m2.group(1).strip()

    if uploaded_str:
        result["uploaded"] = uploaded_str
        result["uploaded_bytes"] = _parse_size(uploaded_str)
    if downloaded_str:
        result["downloaded"] = downloaded_str
        result["downloaded_bytes"] = _parse_size(downloaded_str)
    if debug:
        debug_info["matched_labels"]["uploaded_raw"] = uploaded_str or "(not found)"
        debug_info["matched_labels"]["downloaded_raw"] = downloaded_str or "(not found)"
        debug_info["matched_labels"]["transfer_cell_text"] = (transfer_cell_text[:200] if transfer_cell_text else "(not found)")

    ratio = 0.0
    ratio_str = _find_cell_value(pairs, ["分享率", "Share ratio", "Ratio"])
    if ratio_str:
        ratio_str = ratio_str.strip()
        if ratio_str in ("∞", "Inf", "inf"):
            ratio = float("inf")
        else:
            m = re.search(r'([\d.]+)', ratio_str)
            if m:
                try:
                    ratio = float(m.group(1))
                except ValueError:
                    pass
    if not ratio:
        ratio = _extract_ratio(html)
    if ratio:
        result["ratio"] = ratio
    if debug:
        debug_info["matched_labels"]["ratio_raw"] = str(ratio) if ratio else "(not found)"

    bonus_labels = [
        "魔力值", "魔力", "Karma Points", "Bonus", "积分", "做种积分",
        "电力值", "魅力值", "銀幣", "金币",
    ]
    bonus_str = _find_cell_value(pairs, bonus_labels)
    if not bonus_str:
        bonus_str = _extract_field(html, ["魔力值", "魔力", "Bonus", "积分", "做种积分"])
    if bonus_str:
        m = re.search(r'([\d,]+\.?\d*)', bonus_str)
        if m:
            try:
                result["bonus"] = float(m.group(1).replace(",", ""))
            except ValueError:
                result["bonus"] = bonus_str
    if debug:
        debug_info["matched_labels"]["bonus_raw"] = bonus_str or "(not found)"

    seeding_str = _find_cell_value(pairs, ["做种数", "做种", "Seeding", "做种中"])
    if not seeding_str:
        seeding_str = _extract_field(html, ["做种数", "做种", "Seeding"])
    if seeding_str:
        m = re.search(r'([\d,]+)', seeding_str)
        if m:
            try:
                result["seeding"] = int(m.group(1).replace(",", ""))
            except ValueError:
                pass
    if debug:
        debug_info["matched_labels"]["seeding_raw"] = seeding_str or "(not found)"

    seeding_size_str = _find_cell_value(pairs, ["做种量", "Seeding size", "做种体积"])
    if not seeding_size_str:
        seeding_size_str = _extract_field(html, ["做种量", "Seeding size", "做种体积"])
    if seeding_size_str:
        m = re.search(r'([\d,.\s]+(?:TB|GB|MB|KB|B))', seeding_size_str, re.IGNORECASE)
        if m:
            result["seeding_size"] = m.group(1).strip()
    if debug:
        debug_info["matched_labels"]["seeding_size_raw"] = seeding_size_str or "(not found)"

    # --- Phase 2: /userdetails.php ---
    try:
        detail_html = _fetch_page(f"{base_url}/userdetails.php", cookie, proxy=proxy, timeout=15)
        detail_pairs = _extract_table_cells(detail_html)

        level2 = ""
        level_cell_html = _find_cell_html(detail_pairs, ["等级", "等級", "Class", "User class", "用户等级"])
        if level_cell_html:
            img_title_m = re.search(r'<img[^>]+title\s*=\s*["\']([^"\']+)["\']', level_cell_html, re.IGNORECASE)
            if img_title_m:
                level2 = img_title_m.group(1).strip()
        if not level2:
            level2 = _find_cell_value(detail_pairs, ["等级", "等級", "Class", "User class", "用户等级"])
        if not level2:
            level2 = _extract_text_field(detail_html, ["等级", "Class", "User class", "用户等级"])
        if level2:
            result["level"] = level2
        if debug:
            debug_info["matched_labels"]["level_phase2"] = level2 or "(not found)"

        # Join time
        join_time = _find_cell_value(detail_pairs, ["加入日期", "Join date", "注冊日期", "注册日期"])
        if not join_time:
            join_time = _extract_text_field(detail_html, ["加入日期", "Join date"])
        if join_time:
            result["join_time"] = join_time

        # Donor flag
        is_donor = False
        if re.search(r'<img[^>]+alt\s*=\s*["\']Donor["\']', detail_html, re.IGNORECASE):
            is_donor = True
        elif re.search(r'<img[^>]+src\s*=\s*["\'][^"\']*flag[^"\']*["\']', detail_html, re.IGNORECASE):
            is_donor = True
        if is_donor:
            result["is_donor"] = True

        # H&R count
        hnr_match = re.search(r'href\s*=\s*["\'][^"\']*myhr\.php[^"\']*["\'][^>]*>\s*([\d]+)\s*/\s*([\d]+)', detail_html)
        if hnr_match:
            result["hnr_count"] = f"{hnr_match.group(1)}/{hnr_match.group(2)}"
        else:
            hnr_match2 = re.search(r'([\d]+)\s*/\s*([\d]+)[^<]*(?:<[^>]+>)*\s*(?:<a[^>]*myhr\.php)', detail_html)
            if hnr_match2:
                result["hnr_count"] = f"{hnr_match2.group(1)}/{hnr_match2.group(2)}"

        # Uploads count
        uploads_str = _find_cell_value(detail_pairs, ["发布", "上传种数", "Uploads"])
        if not uploads_str:
            uploads_str = _extract_field(detail_html, ["发布", "上传种数", "Uploads"])
        if not uploads_str:
            uploads_str = _extract_text_field(detail_html, ["发布", "上传种数", "Uploads"])
        if uploads_str:
            result["uploads"] = uploads_str

        # Seeding stats from userdetails (some sites put them here)
        seeding_stats_text = _find_cell_value(detail_pairs, ["做种统计", "当前做种", "做种中"])
        if seeding_stats_text and "seeding" not in result:
            m = re.search(r'([\d,]+)', seeding_stats_text)
            if m:
                try:
                    result["seeding"] = int(m.group(1).replace(",", ""))
                except ValueError:
                    pass
        if seeding_stats_text and "seeding_size" not in result:
            m = re.search(r'([\d,.\s]+(?:TB|GB|MB|KB|B))', seeding_stats_text, re.IGNORECASE)
            if m:
                result["seeding_size"] = m.group(1).strip()

    except Exception:
        pass

    # --- Phase 3: /mybonus.php ---
    try:
        bonus_html = _fetch_page(f"{base_url}/mybonus.php", cookie, proxy=proxy, timeout=15)

        bph_match = re.search(
            r'(?:每小时|per hour|当前每小时能获取)(?:[^<\d]*?)([\d,.]+)',
            bonus_html, re.IGNORECASE)
        if bph_match:
            try:
                result["bonus_per_hour"] = float(bph_match.group(1).replace(",", ""))
            except ValueError:
                result["bonus_per_hour"] = bph_match.group(1)

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

    has_data = any(k in result for k in ("uploaded", "downloaded", "ratio", "bonus", "seeding"))
    if not has_data:
        result["status"] = "error"
        result["error"] = "Could not parse profile data from page"

    if debug_info is not None:
        result["_debug"] = debug_info

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


def _parse_ttg_profile(site_id, site_cfg, cookie, debug=False):
    """Scrape TTG user profile from 3 pages (index + userdetails + mybonus)."""
    result = {"status": "ok"}
    base_url = site_cfg["url"].rstrip("/")
    proxy = _env("PT_PROXY") if site_cfg.get("needs_proxy") else None

    debug_info = None
    if debug:
        debug_info = {"matched_labels": {}}

    try:
        html = _fetch_page(f"{base_url}/index.php", cookie, proxy=proxy, timeout=15)
    except Exception as e:
        return {"status": "error", "error": str(e)[:120]}

    if _is_login_page(html):
        return {"status": "error", "error": "Cookie expired"}

    if debug:
        title_m = re.search(r'<title>([^<]*)</title>', html, re.IGNORECASE)
        debug_info["page_title"] = title_m.group(1).strip() if title_m else ""
        debug_info["info_html_excerpt"] = html[:2000]

    username = _extract_text_field(html, ["用户名", "Username"])
    if username:
        result["username"] = username
    if debug:
        debug_info["matched_labels"]["username"] = username or ""

    uploaded_str = _extract_field(html, ["上传量", "上传", "Uploaded"])
    if uploaded_str:
        result["uploaded"] = uploaded_str
        result["uploaded_bytes"] = _parse_size(uploaded_str)
    if debug:
        debug_info["matched_labels"]["uploaded_raw"] = uploaded_str or ""

    downloaded_str = _extract_field(html, ["下载量", "下载", "Downloaded"])
    if downloaded_str:
        result["downloaded"] = downloaded_str
        result["downloaded_bytes"] = _parse_size(downloaded_str)
    if debug:
        debug_info["matched_labels"]["downloaded_raw"] = downloaded_str or ""

    ratio = _extract_ratio(html)
    if ratio:
        result["ratio"] = ratio
    if debug:
        debug_info["matched_labels"]["ratio_raw"] = str(ratio) if ratio else ""

    try:
        bonus_html = _fetch_page(f"{base_url}/mybonus.php", cookie, proxy=proxy, timeout=15)
        bonus_str = _extract_field(bonus_html, ["做种积分", "魔力值", "Bonus", "积分"])
        if bonus_str:
            try:
                result["bonus"] = float(bonus_str.replace(",", ""))
            except ValueError:
                result["bonus"] = bonus_str
        if debug:
            debug_info["matched_labels"]["bonus_raw"] = bonus_str or ""
    except Exception:
        pass

    has_data = any(k in result for k in ("uploaded", "downloaded", "ratio", "bonus"))
    if not has_data:
        result["status"] = "error"
        result["error"] = "Could not parse profile data from page"

    if debug_info is not None:
        result["_debug"] = debug_info

    return result


def _fetch_site_profile(site_id, site_cfg, cookies, debug=False):
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
        return _parse_nexusphp_profile(site_id, site_cfg, cookie, debug=debug)

    if site_cfg.get("parser") == "ttg":
        return _parse_ttg_profile(site_id, site_cfg, cookie, debug=debug)

    return {"status": "error", "error": f"Unknown parser: {site_cfg.get('parser')}"}


def main():
    _load_env_file()

    args = sys.argv[1:]
    filter_site = None
    json_output = True
    query_all = False
    debug = False

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--site" and i + 1 < len(args):
            filter_site = args[i + 1]
            i += 1
        elif arg == "--json":
            json_output = True
        elif arg == "--all":
            query_all = True
        elif arg == "--debug":
            debug = True
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
    api_key = _env("MTEAM_API_KEY", "")

    if filter_site:
        target_sites = {filter_site: SITES[filter_site]}
    elif query_all:
        target_sites = dict(SITES)
    else:
        # Default: only sites with cookies configured or mteam with API key
        target_sites = {}
        for sid, scfg in SITES.items():
            if sid == "mteam" and api_key:
                target_sites[sid] = scfg
            elif cookies.get(sid):
                target_sites[sid] = scfg

    configured_count = len(target_sites)
    total_count = len(SITES)
    print(f"Querying {configured_count} sites ({configured_count} configured, use --all for all {total_count})",
          file=sys.stderr)

    profiles = {}
    for site_id, site_cfg in target_sites.items():
        log.info("querying profile site=%s", site_id)
        profiles[site_id] = _fetch_site_profile(site_id, site_cfg, cookies, debug=debug)

    print(json.dumps(profiles, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
