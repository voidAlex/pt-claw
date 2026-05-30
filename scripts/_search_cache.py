#!/usr/bin/env python3
"""
Search result cache — avoid repeated requests during batch operations.

Used by cross_seed.py batch-scan to prevent hitting site rate limits.

Cache file: scripts/pt_search_cache.json
TTL: 5 minutes (300 seconds)

Usage (from other scripts):
    from _search_cache import cache_get, cache_put
    cached = cache_get("mteam", "流浪地球2")
    if cached is not None:
        return cached
    results = ...  # do actual search
    cache_put("mteam", "流浪地球2", results)
"""

import json
import os
import time

_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pt_search_cache.json")
_TTL = 300


def _load_cache() -> dict:
    if not os.path.exists(_CACHE_FILE):
        return {}
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict):
    with open(_CACHE_FILE, "w") as f:
        json.dump(cache, f, ensure_ascii=False)


def _cache_key(site_id: str, query: str) -> str:
    return f"{site_id}:{query}"


def cache_get(site_id: str, query: str, ttl: int = _TTL) -> list | None:
    cache = _load_cache()
    key = _cache_key(site_id, query)
    entry = cache.get(key)
    if entry is None:
        return None
    if time.time() - entry.get("ts", 0) > ttl:
        return None
    return entry.get("data")


def cache_put(site_id: str, query: str, data: list):
    cache = _load_cache()
    key = _cache_key(site_id, query)
    cache[key] = {"ts": time.time(), "data": data}
    # Evict expired entries
    now = time.time()
    expired = [k for k, v in cache.items() if now - v.get("ts", 0) > _TTL * 2]
    for k in expired:
        del cache[k]
    _save_cache(cache)


def cache_clear():
    if os.path.exists(_CACHE_FILE):
        os.remove(_CACHE_FILE)
