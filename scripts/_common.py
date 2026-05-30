"""Shared utilities for pt-claw scripts."""
import os, re

_skill_dir = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(_skill_dir, "..", "secrets.env")
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
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                _env_cache[k.strip()] = v.strip()


def _env(key, default=""):
    val = os.environ.get(key, "")
    if not val:
        _load_env_file()
        val = _env_cache.get(key, default)
    return val


def _env_matching(prefix):
    _load_env_file()
    result = {}
    for k, v in os.environ.items():
        if k.startswith(prefix):
            result[k] = v
    for k, v in _env_cache.items():
        if k.startswith(prefix) and k not in result:
            result[k] = v
    return result


def _fmt_size(size_bytes):
    if size_bytes == 0:
        return ""
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
    "加群", "QQ", "微信", "tg", "广告", "推广", "福利", "免费", "导航",
    "合集", "大合集", "まとめ", "pack", "collection", "全作品",
    "预告", "宣传片", "sample", "trailer", "预览",
]
PREFERRED_TAGS = [
    "FHDC", "HD", "4K", "中文字幕", "H265", "HEVC", "uncensored",
    "破解", "無碼", "Reducing Mosaic", "破坏版", "破壊版", "RM", "leak",
    "无码", "字幕", "-C", "-ch",
]


def _is_spam(title):
    for kw in AD_KEYWORDS:
        if kw.lower() in title.lower():
            return True
    if re.match(r'^[a-f0-9]{40}$', title.strip(), re.I):
        return True
    return False


def _magnet_score(title):
    s = 0
    for tag in PREFERRED_TAGS:
        if tag.lower() in title.lower():
            s += 1
    return s
