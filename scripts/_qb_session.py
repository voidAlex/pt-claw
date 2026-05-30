"""Shared qBittorrent session — single login, reusable across all scripts."""
import json, os, urllib.request, urllib.parse, urllib.error
from http.cookiejar import CookieJar

from _common import _env

_opener = None
_url = None


def get_session():
    """Return (opener, base_url) — logs in once, reuses session cookie."""
    global _opener, _url
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
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError("qBittorrent login failed — check credentials")
        raise
    return _opener, _url


def qb_request(endpoint, method="GET", data=None, timeout=30):
    """Make an authenticated request to qBittorrent Web API."""
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
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e}"}


def reset():
    """Reset cached session (use after credential changes)."""
    global _opener, _url
    _opener = None
    _url = None
