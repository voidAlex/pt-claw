"""Shared utilities for pt-claw scripts.

Eliminates _env/_load_env_file/_fmt_size duplication across 16+ scripts.
"""
import os

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
    """Return dict of all env vars whose key starts with prefix (env + secrets.env)."""
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
