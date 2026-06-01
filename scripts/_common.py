"""Shared utilities for pt-claw scripts."""
from __future__ import annotations
import json, os, re, threading

from _logger import get_logger

log = get_logger("_common")

_skill_dir = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(_skill_dir, "..", "secrets.env")
_env_cache = None
_env_lock = threading.Lock()


def _load_env_file():
    global _env_cache
    if _env_cache is not None:
        return
    with _env_lock:
        if _env_cache is not None:
            return
        _env_cache = {}
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    v = v.strip()
                    # Strip surrounding quotes if present (e.g. KEY="value")
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                        v = v[1:-1]
                    _env_cache[k.strip()] = v
            log.debug("loaded env file path=%s keys=%d", ENV_FILE, len(_env_cache))


def _env(key, default=""):
    """Read config value. secrets.env takes priority over os.environ.

    Rationale: the Hermes process may have stale values in os.environ from
    a previous secrets.env version.  The file on disk is the source of truth;
    process environment is only a fallback for keys not present in the file.

    If the key exists in secrets.env (even with empty value), that value is
    returned as-is — the user explicitly set it.  Only keys absent from the
    file fall through to os.environ.
    """
    _load_env_file()
    if key in _env_cache:
        return _env_cache[key]
    return os.environ.get(key, default)


def _env_matching(prefix):
    _load_env_file()
    result = {}
    # secrets.env first (authoritative)
    for k, v in _env_cache.items():
        if k.startswith(prefix):
            result[k] = v
    # os.environ fills in keys NOT already in file
    for k, v in os.environ.items():
        if k.startswith(prefix) and k not in result:
            result[k] = v
    return result


def _fmt_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def _parse_size(size_str):
    """Parse human-readable size string like '4.37 GB' to bytes."""
    m = re.match(r'([\d.,]+)\s*(TB|GB|MB|KB|B)', size_str, re.IGNORECASE)
    if not m:
        return 0
    val = float(m.group(1).replace(",", ""))
    unit = m.group(2).upper()
    mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return int(val * mult.get(unit, 1))


def _fmt_speed(b):
    if b == 0:
        return "0"
    for u in ('B/s', 'KB/s', 'MB/s', 'GB/s'):
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB/s"


def parse_arg(args, flag, default=None):
    for i, a in enumerate(args):
        if a == flag and i + 1 < len(args):
            return args[i + 1]
    return default


def flag_present(args, flag):
    return flag in args


# Public torrent cleanup constants
PUBLIC_TAGS = {"sukebei", "javbus"}
MAX_DELETE_PER_RUN = 50
MAX_PUBLIC_RATIO = 0.20
COMPLETED_STATES = {"pausedUP", "uploading", "forcedUP", "stalledUP"}


# Spam filter for public magnet sources (sukebei, javbus)
AD_KEYWORDS = [
    # Social media / contact spam
    "加群", "QQ", "微信", "tg", "广告", "推广", "福利", "免费", "导航",
    "telegram", "二维码", "扫码", "关注", "点赞", "订阅", "私信",
    "交流群", "VIP", "会员", "独家",
    # Pack/collection spam
    "合集", "大合集", "まとめ", "pack", "collection", "全作品",
    # Preview/sample spam
    "预告", "宣传片", "sample", "trailer", "预览",
    # English trust spam
    "no virus", "verified", "clean", "fast download", "high speed",
    # Watermark bait
    "无水印", "去水印", "原版", "无毒",
    # URL spam (detected separately below)
]
# PREFERRED_TAGS: weighted scoring for magnet quality ranking
TAG_WEIGHTS = {
    "4K": 3, "FHDC": 3,
    "中文字幕": 2, "字幕": 2, "H265": 2, "HEVC": 2,
    "uncensored": 2, "破解": 2, "無碼": 2, "无码": 2,
    "leak": 2, "Reducing Mosaic": 2, "破坏版": 2, "破壊版": 2,
    "HD": 1, "RM": 1, "-C": 1, "-ch": 1,
}
NEGATIVE_TAGS = ["CAM", "TS", "CAMRIP", "HDCAM", "HDTC", "HDTS", "SCR"]
NEGATIVE_WEIGHT = -2


def _is_spam(title):
    t = title.strip().lower()
    if not t:
        return False
    # Pure hex hash
    if re.match(r'^[a-f0-9]{40}$', t, re.I):
        return True
    # Keyword matching — use word boundary for short keywords to avoid false positives
    short_kw = {"tg", "QQ", "VIP"}
    for kw in AD_KEYWORDS:
        kwl = kw.lower()
        if kw in short_kw:
            if re.search(rf'\b{re.escape(kwl)}\b', t):
                return True
        elif kwl in t:
            return True
    # URL patterns
    if re.search(r'https?://|www\.|\.com\b|\.cn\b|t\.me/', t, re.I):
        return True
    return False


def _magnet_score(title):
    t = title.lower()
    s = sum(w for tag, w in TAG_WEIGHTS.items() if tag.lower() in t)
    for tag in NEGATIVE_TAGS:
        if tag.lower() in t:
            s += NEGATIVE_WEIGHT
    return s


def _is_login_page(html: str) -> bool:
    """Check if an HTML page is a login page by examining the <title> tag.

    This avoids false positives from nav text like '快捷登录' appearing in
    normal page headers. A login page has a title like '登录 - PTTime' while
    a normal torrent listing will have a different title.
    """
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if not title_match:
        return False
    title_text = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
    return '登录' in title_text or 'login' in title_text.lower()


# ── Wishlist filtering ─────────────────────────────────────────

WISHLIST_PATH = os.path.join(_skill_dir, "..", "pt_wishlist.json")


def _load_wishlist() -> dict | None:
    if not os.path.exists(WISHLIST_PATH):
        return None
    try:
        with open(WISHLIST_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _get_actor_filters(actor_name: str) -> dict | None:
    """Get exclude_prefixes and require_freeleech for an actor from wishlist."""
    wl = _load_wishlist()
    if not wl:
        return None
    for actor in wl.get("actors", []):
        if actor.get("name") == actor_name:
            return {
                "exclude_prefixes": actor.get("exclude_prefixes", []),
                "require_freeleech": actor.get("require_freeleech", False),
            }
    return None


def _filter_by_wishlist(results: list[dict], actor_name: str) -> list[dict]:
    """Filter search results by wishlist rules for an actor.

    Supports exclude_prefixes (skip torrents whose fanhao code starts
    with an excluded prefix) and require_freeleech (only keep Free/2xFree).
    Returns filtered list; returns unchanged if no rules apply.
    """
    filters = _get_actor_filters(actor_name)
    if not filters:
        return results
    exclude = [p.upper() for p in filters.get("exclude_prefixes", [])]
    freeleech_only = filters.get("require_freeleech", False)
    filtered = []
    for r in results:
        title = r.get("title", "")
        code_match = re.match(r'^([A-Za-z0-9]+-\d+)', title)
        code = code_match.group(1).upper() if code_match else ""
        if exclude and any(code.startswith(p) for p in exclude):
            continue
        if freeleech_only and r.get("promo", "") not in ("Free", "2xFree"):
            continue
        filtered.append(r)
    return filtered
