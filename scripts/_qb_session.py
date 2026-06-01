"""Shared qBittorrent session — single login, reusable across all scripts."""
import json, os, threading, urllib.request, urllib.parse, urllib.error
from http.cookiejar import CookieJar

from _common import _env
from _logger import get_logger

log = get_logger("qb_session")

_opener = None
_url = None
_lock = threading.Lock()


def get_session():
    """Return (opener, base_url) — logs in once, reuses session cookie."""
    global _opener, _url
    if _opener is not None:
        return _opener, _url
    with _lock:
        if _opener is not None:
            return _opener, _url

        _url = _env("QBITTORRENT_URL", "").rstrip("/")
        qb_user = _env("QBITTORRENT_USER", "")
        qb_pass = _env("QBITTORRENT_PASS", "")

        if not all([_url, qb_user, qb_pass]):
            raise RuntimeError("QBITTORRENT_URL/USER/PASS not set")

        cj = CookieJar()
        _opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        _opener.addheaders = [("User-Agent", "Hermes/1.0")]
        login_data = urllib.parse.urlencode({"username": qb_user, "password": qb_pass}).encode()
        try:
            _opener.open(f"{_url}/api/v2/auth/login", login_data, timeout=10)
            log.info("qBittorrent login success url=%s", _url)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                log.error("qBittorrent login failed url=%s status=403", _url)
                raise RuntimeError("qBittorrent login failed — check credentials")
            log.error("qBittorrent login error url=%s status=%s", _url, e.code)
            raise
        return _opener, _url


def qb_request(endpoint, method="GET", data=None, timeout=30):
    """Make an authenticated request to qBittorrent Web API, with auto re-auth."""
    return _qb_request_inner(endpoint, method, data, timeout)


def _qb_request_inner(endpoint, method="GET", data=None, timeout=30, _retry=True):
    global _opener
    opener, base_url = get_session()
    full_url = f"{base_url}{endpoint}"
    if method == "POST" and data:
        req = urllib.request.Request(full_url,
                                     data=urllib.parse.urlencode(data).encode(),
                                     method=method)
    else:
        req = urllib.request.Request(full_url, method=method)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            if not raw.strip():
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw.decode("utf-8", errors="replace").strip()}
    except urllib.error.HTTPError as e:
        if _retry and e.code in (403, 401):
            log.warning("qb auth failure (HTTP %d), re-authenticating...", e.code)
            with _lock:
                _opener = None
            return _qb_request_inner(endpoint, method, data, timeout, _retry=False)
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        if _retry:
            log.warning("qb connection error, re-authenticating...")
            with _lock:
                _opener = None
            return _qb_request_inner(endpoint, method, data, timeout, _retry=False)
        return {"error": f"Connection failed: {e}"}


def reset():
    """Reset cached session (use after credential changes)."""
    global _opener, _url
    log.info("session reset")
    _opener = None
    _url = None
