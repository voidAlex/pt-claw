#!/usr/bin/env python3
"""
Connectivity check — test external service connections.

Usage:
    python3 connectivity_check.py                          # test all
    python3 connectivity_check.py --quick                  # skip slow PT site tests
    python3 connectivity_check.py qb                       # test only qBittorrent
    python3 connectivity_check.py mteam                    # test only M-Team API
    python3 connectivity_check.py jf                       # test only Jellyfin
    python3 connectivity_check.py jf1                      # test only Jellyfin adult
    python3 connectivity_check.py jf2                      # test only Jellyfin movie/tv
    python3 connectivity_check.py javbus                   # test only javbus-api
    python3 connectivity_check.py proxy                    # test only PT_PROXY
    python3 connectivity_check.py --keepalive             # keepalive all PT sites
    python3 connectivity_check.py --keepalive --site btschool  # keepalive one site
"""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error

_skill_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _skill_dir)

# Proxy compatibility: ProxyHandler breaks with certain proxy types
from _proxy import using_proxy

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
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    _env_cache[k.strip()] = v.strip()


def _env(key, default=""):
    val = os.environ.get(key, "")
    if not val:
        _load_env_file()
        val = _env_cache.get(key, default)
    return val


results = []


def _result(name, status, detail="", latency_ms=0):
    r = {"service": name, "status": status, "detail": detail}
    if latency_ms:
        r["latency_ms"] = round(latency_ms)
    results.append(r)
    icon = {"ok": "✅", "warn": "⚠️", "fail": "❌", "skip": "⏭️"}[status]
    extra = f" ({latency_ms:.0f}ms)" if latency_ms else ""
    print(f"  {icon} {name}: {detail}{extra}")


def _fetch(url, timeout=10, headers=None, data=None, proxy=None):
    """Return (status_code, body_text, elapsed_ms) or raise."""
    with using_proxy(proxy):
        opener = urllib.request.build_opener()
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        t0 = time.time()
        if data:
            if isinstance(data, dict):
                data = urllib.parse.urlencode(data).encode()
            req.data = data
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    elapsed = (time.time() - t0) * 1000
    return status, body, elapsed


def test_qbittorrent():
    print("\n=== qBittorrent ===")
    url = _env("QBITTORRENT_URL")
    user = _env("QBITTORRENT_USER")
    passwd = _env("QBITTORRENT_PASS")
    if not all([url, user, passwd]):
        _result("qBittorrent", "fail", "QBITTORRENT_URL/USER/PASS not set")
        return
    try:
        data = urllib.parse.urlencode({"username": user, "password": passwd}).encode()
        t0 = time.time()
        req = urllib.request.Request(f"{url.rstrip('/')}/api/v2/auth/login", data=data)
        req.add_header("User-Agent", "Hermes/1.0")
        opener = urllib.request.build_opener()
        with opener.open(req, timeout=10) as resp:
            elapsed = (time.time() - t0) * 1000
            cookies = resp.headers.get_all("Set-Cookie", [])
            sid = any("SID=" in c for c in cookies)
        if sid:
            _result("qBittorrent", "ok", f"login OK, {url}", elapsed)
        else:
            _result("qBittorrent", "warn", f"login returned 200 but no SID cookie", elapsed)
    except urllib.error.HTTPError as e:
        _result("qBittorrent", "fail", f"HTTP {e.code}")
    except Exception as e:
        _result("qBittorrent", "fail", str(e)[:80])


def test_mteam():
    print("\n=== M-Team API ===")
    key = _env("MTEAM_API_KEY")
    if not key:
        _result("M-Team", "fail", "MTEAM_API_KEY not set")
        return
    try:
        body = json.dumps({"keyword": "test", "page": 1, "size": 1}).encode()
        req = urllib.request.Request(
            "https://api.m-team.cc/api/torrent/search",
            data=body,
            headers={"x-api-key": key, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        proxy = _env("PT_PROXY")
        t0 = time.time()
        with using_proxy(proxy):
            opener = urllib.request.build_opener()
            with opener.open(req, timeout=15) as resp:
                elapsed = (time.time() - t0) * 1000
                data = json.loads(resp.read())
        code = str(data.get("code", ""))
        if code == "0":
            total = data.get("data", {}).get("total", "?")
            _result("M-Team", "ok", f"API OK, search returned {total} results", elapsed)
        else:
            _result("M-Team", "fail", f"API returned code={code}, message={data.get('message', '')[:60]}", elapsed)
    except urllib.error.HTTPError as e:
        detail = f"HTTP {e.code}"
        if e.code == 403:
            detail += " (rate limited or invalid key)"
        elif e.code == 405:
            detail += " (API endpoint down)"
        _result("M-Team", "fail", detail)
    except Exception as e:
        _result("M-Team", "fail", str(e)[:80])


def test_jellyfin(instance, url_key, token_key):
    label = f"Jellyfin {instance}"
    print(f"\n=== {label} ===")
    url = _env(url_key)
    token = _env(token_key)
    if not all([url, token]):
        _result(label, "skip", f"{url_key} or {token_key} not set")
        return
    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/System/Info",
            headers={"X-MediaBrowser-Token": token, "User-Agent": "Hermes/1.0"},
        )
        t0 = time.time()
        opener = urllib.request.build_opener()
        with opener.open(req, timeout=10) as resp:
            elapsed = (time.time() - t0) * 1000
            info = json.loads(resp.read())
        version = info.get("Version", "?")
        product = info.get("ProductName", "?")
        _result(label, "ok", f"{product} {version} @ {url}", elapsed)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            _result(label, "fail", f"401 Unauthorized — bad API key")
        else:
            _result(label, "fail", f"HTTP {e.code}")
    except Exception as e:
        _result(label, "fail", str(e)[:80])


def test_javbus_api():
    print("\n=== javbus-api ===")
    url = _env("JAVBUS_API_URL")
    if not url:
        _result("javbus-api", "skip", "JAVBUS_API_URL not set")
        return
    try:
        status, body, elapsed = _fetch(f"{url.rstrip('/')}/api/movies/ABP-001", timeout=10)
        if status == 200:
            data = json.loads(body)
            if data.get("id"):
                _result("javbus-api", "ok", f"Docker API OK @ {url}", elapsed)
            else:
                _result("javbus-api", "warn", f"API responded but no data for test code", elapsed)
        else:
            _result("javbus-api", "fail", f"HTTP {status}")
    except urllib.error.URLError:
        _result("javbus-api", "fail", "connection refused — container down?")
    except Exception as e:
        _result("javbus-api", "fail", str(e)[:80])


def test_proxy():
    print("\n=== PT_PROXY ===")
    proxy = _env("PT_PROXY")
    if not proxy:
        _result("PT_PROXY", "warn", "not set (sites needing proxy will fail)")
        return
    try:
        status, body, elapsed = _fetch("https://www.google.com", timeout=10, proxy=proxy)
        _result("PT_PROXY", "ok", f"proxy OK ({proxy}), {elapsed:.0f}ms", elapsed)
    except Exception as e:
        _result("PT_PROXY", "fail", f"proxy unreachable: {str(e)[:60]}")


def _test_pt_site(name, base_url, cookie_var, needs_proxy):
    print(f"\n=== {name} ===")
    cookie = _env(cookie_var)
    if not cookie:
        _result(name, "skip", f"{cookie_var} not set")
        return
    pt_proxy = _env("PT_PROXY")
    attempts = [pt_proxy] if needs_proxy else [None, pt_proxy]
    url = f"{base_url.rstrip('/')}/torrents.php?search=test"
    headers = {"Cookie": cookie}
    last_err = None
    for use_proxy in attempts:
        try:
            status, body, elapsed = _fetch(url, timeout=15, headers=headers, proxy=use_proxy)
            if "登录" in body[:3000] or "login" in body[:3000].lower():
                _result(name, "fail", f"cookie expired (login page returned)", elapsed)
                return
            elif "<title>" in body and "403" in body[:500]:
                _result(name, "fail", f"403 Forbidden", elapsed)
                return
            elif "torrent" in body.lower() or "search" in body.lower():
                label = "proxy" if use_proxy else "direct"
                _result(name, "ok", f"site OK ({label}, {len(body)} bytes)", elapsed)
                return
            else:
                _result(name, "warn", f"got {len(body)} bytes, unclear if page is valid", elapsed)
                return
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if len(attempts) > 1:
                continue
        except Exception as e:
            last_err = str(e)[:80]
            if len(attempts) > 1:
                continue
    if last_err:
        detail = last_err
        if "403" in detail:
            detail += " — cookie may be expired or IP blocked"
        _result(name, "fail", detail)
    else:
        _result(name, "fail", "all attempts failed")


def test_pt_sites(filter_site=None):
    try:
        from pt_search import SITES
    except ImportError:
        print("\n⚠️  Cannot import SITES from pt_search.py")
        return

    for site_id, cfg in SITES.items():
        if site_id == "mteam":
            continue
        if filter_site and site_id != filter_site:
            continue
        _test_pt_site(
            name=site_id,
            base_url=cfg["url"],
            cookie_var=f"PT_COOKIE_{site_id.upper()}",
            needs_proxy=cfg.get("needs_proxy", False),
        )


def _keepalive_site(name, base_url, cookie_var, needs_proxy):
    cookie = _env(cookie_var)
    if not cookie:
        print(f"  ⏭️  {name}: {cookie_var} not set, skip")
        return True
    pt_proxy = _env("PT_PROXY")
    attempts = [pt_proxy] if needs_proxy else [None, pt_proxy]
    url = f"{base_url.rstrip('/')}/index.php"
    for use_proxy in attempts:
        try:
            status, body, elapsed = _fetch(url, timeout=15, headers={"Cookie": cookie}, proxy=use_proxy)
            if "登录" in body[:3000] or "login" in body[:3000].lower():
                print(f"  ⚠️  {name}: cookie expired ({elapsed:.0f}ms)")
                return False
            elif status == 200:
                label = "proxy" if use_proxy else "direct"
                print(f"  ✅ {name}: keepalive OK ({label}, {elapsed:.0f}ms)")
                return True
            else:
                print(f"  ❌ {name}: HTTP {status}")
                return False
        except Exception:
            continue
    print(f"  ❌ {name}: all attempts failed")
    return False


def keepalive_sites(filter_site=None):
    try:
        from pt_search import SITES
    except ImportError:
        print("⚠️  Cannot import SITES from pt_search.py")
        return
    print("PT site keepalive (accessing index page to refresh session)")
    print("-" * 50)
    failed = []
    for site_id, cfg in SITES.items():
        if site_id == "mteam":
            continue
        if filter_site and site_id != filter_site:
            continue
        ok = _keepalive_site(
            name=site_id,
            base_url=cfg["url"],
            cookie_var=f"PT_COOKIE_{site_id.upper()}",
            needs_proxy=cfg.get("needs_proxy", False),
        )
        if not ok:
            failed.append(site_id)
    print("-" * 50)
    if not failed:
        print("All sites keepalive OK")
    else:
        print(f"⚠️  {len(failed)} site(s) failed: {', '.join(failed)}")
        cc_host = _env("COOKIE_CLOUD_HOST", "")
        if cc_host:
            print("Attempting CookieCloud sync...")
            sync_script = os.path.join(_skill_dir, "cookie_sync.py")
            if os.path.exists(sync_script):
                for site in failed:
                    os.system(f"python3 {sync_script} --site {site}")
                print("Re-checking failed sites...")
                still_failed = []
                for site_id in failed:
                    cfg = SITES[site_id]
                    ok = _keepalive_site(
                        name=site_id,
                        base_url=cfg["url"],
                        cookie_var=f"PT_COOKIE_{site_id.upper()}",
                        needs_proxy=cfg.get("needs_proxy", False),
                    )
                    if not ok:
                        still_failed.append(site_id)
                if still_failed:
                    print(f"❌ Still failing after sync: {', '.join(still_failed)} — manual login needed")
                else:
                    print("✅ CookieCloud sync resolved all failures")
            else:
                print("⚠️  cookie_sync.py not found")
        else:
            print("💡 Tip: Configure CookieCloud for automatic cookie sync (see templates/docker-compose.cookiecloud.yml)")


SERVICE_MAP = {
    "qb": lambda: test_qbittorrent(),
    "mteam": lambda: test_mteam(),
    "jf": lambda: (test_jellyfin("adult", "JELLYFIN1_URL", "JELLYFIN1_API_KEY"),
                    test_jellyfin("movie/tv", "JELLYFIN2_URL", "JELLYFIN2_API_KEY")),
    "jf1": lambda: test_jellyfin("adult", "JELLYFIN1_URL", "JELLYFIN1_API_KEY"),
    "jf2": lambda: test_jellyfin("movie/tv", "JELLYFIN2_URL", "JELLYFIN2_API_KEY"),
    "javbus": lambda: test_javbus_api(),
    "proxy": lambda: test_proxy(),
}


def main():
    _load_env_file()

    args = sys.argv[1:]
    only_site = None
    quick = False
    only_service = None
    keepalive = False

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--quick":
            quick = True
        elif arg == "--keepalive":
            keepalive = True
        elif arg == "--site" and i + 1 < len(args):
            i += 1
            only_site = args[i]
        elif arg == "--json":
            pass
        elif arg in SERVICE_MAP or arg in ("pt", "sites"):
            only_service = arg
        elif arg.startswith("-"):
            pass
        else:
            only_service = arg
        i += 1

    print("pt-claw connectivity check")
    print("=" * 50)

    if keepalive:
        keepalive_sites(filter_site=only_site)
        return

    if only_service:
        if only_service in SERVICE_MAP:
            SERVICE_MAP[only_service]()
        elif only_service in ("pt", "sites"):
            test_pt_sites(filter_site=only_site)
        else:
            print(f"Unknown service: {only_service}")
            print(f"Available: {', '.join(list(SERVICE_MAP.keys()) + ['pt', 'sites'])}")
            sys.exit(1)
    elif only_site:
        test_pt_sites(filter_site=only_site)
    else:
        test_qbittorrent()
        test_mteam()
        test_jellyfin("adult", "JELLYFIN1_URL", "JELLYFIN1_API_KEY")
        test_jellyfin("movie/tv", "JELLYFIN2_URL", "JELLYFIN2_API_KEY")
        test_javbus_api()
        test_proxy()
        if not quick:
            test_pt_sites()
        else:
            print("\n⏭️  PT sites skipped (--quick)")

    print("\n" + "=" * 50)
    ok = sum(1 for r in results if r["status"] == "ok")
    warn = sum(1 for r in results if r["status"] == "warn")
    fail = sum(1 for r in results if r["status"] == "fail")
    skip = sum(1 for r in results if r["status"] == "skip")
    total = len(results)
    print(f"Results: {ok}/{total} OK, {warn} warn, {fail} fail, {skip} skip")

    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    sys.exit(1 if fail > 0 else 0)


if __name__ == "__main__":
    main()
