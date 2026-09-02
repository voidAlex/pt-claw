#!/usr/bin/env python3
"""Regression probe: localhost requests must NOT go through PT_PROXY; remote ones must.

History: 2026-08-24 the chase cron went silently dead because javbus_star.py passed
PT_PROXY to the local javbus-api (localhost:8922). The proxy resolves `localhost` to
the proxy box itself, which has no :8922 service -> deterministic HTTP 502. Fixed
2026-08-26 with host-gated proxy in javbus_star.javbus_get() and javbus_magnet._get_json().
Run this probe after any change to _http.py or proxy handling to catch regressions.

Usage:
    python3 scripts/verify_javbus_proxy.py
Exit code 0 = all checks passed; 1 = failure. Prints PASS/FAIL per check.
"""
import os
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)

import javbus_star  # noqa: E402
import javbus_magnet  # noqa: E402

from _common import _env  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  | {detail}" if detail else ""))


captured = {}


def fake_fetch_json(url, **kw):
    captured["proxy"] = kw.get("proxy")
    return {}, 0.0


orig_star = javbus_star.fetch_json
orig_magnet = javbus_magnet.fetch_json
javbus_star.fetch_json = fake_fetch_json
javbus_magnet.fetch_json = fake_fetch_json

try:
    # A. localhost / loopback must never get a proxy (the original bug)
    javbus_star.javbus_get("/api/movies/search?keyword=test")
    check("javbus_star.javbus_get(localhost) -> proxy None",
          captured.get("proxy") is None, f"proxy={captured.get('proxy')!r}")

    javbus_star.JAVBUS_API = "http://127.0.0.1:8922"
    javbus_star.javbus_get("/api/movies/search?keyword=test")
    check("javbus_star.javbus_get(127.0.0.1) -> proxy None",
          captured.get("proxy") is None, f"proxy={captured.get('proxy')!r}")
    javbus_star.JAVBUS_API = "http://localhost:8922"

    javbus_magnet._get_json("http://localhost:8922/api/movies/SNOS-151")
    check("javbus_magnet._get_json(localhost) -> proxy None",
          captured.get("proxy") is None, f"proxy={captured.get('proxy')!r}")

    # B. remote hosts must keep getting PT_PROXY (do not break intended proxying)
    pt_proxy = _env("PT_PROXY") or None
    javbus_star.JAVBUS_API = "http://example.com:8922"
    javbus_star.javbus_get("/api/movies/search?keyword=test")
    check("javbus_star.javbus_get(remote) -> proxy=PT_PROXY",
          captured.get("proxy") == pt_proxy,
          f"proxy={captured.get('proxy')!r} pt_proxy={pt_proxy!r}")
    javbus_star.JAVBUS_API = "http://localhost:8922"

    javbus_magnet._get_json("http://example.com:8922/api/movies/SNOS-151")
    check("javbus_magnet._get_json(remote) -> proxy=PT_PROXY",
          captured.get("proxy") == pt_proxy,
          f"proxy={captured.get('proxy')!r} pt_proxy={pt_proxy!r}")
finally:
    javbus_star.fetch_json = orig_star
    javbus_magnet.fetch_json = orig_magnet

# C. live end-to-end against local javbus-api (no monkeypatch). Fails loudly if the
# container is down — that is a separate concern from proxy gating.
try:
    data = javbus_star.javbus_get(
        "/api/movies/search?keyword=浅野こころ&page=1&type=normal")
    n = len(data.get("movies", []))
    check("live javbus_star.javbus_get(浅野こころ) -> movies>0", n > 0, f"movies={n}")
except Exception as e:
    check("live javbus_star.javbus_get(浅野こころ)", False, str(e)[:120])

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
