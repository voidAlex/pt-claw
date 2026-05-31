"""
Shared HTTP client with connection pooling, retry, and proxy warmup.

Backed by urllib3 PoolManager for true TCP connection reuse across all scripts.
Drop-in replacement for the scattered urllib.request.build_opener() pattern.

Usage:
    from _http import fetch

    # Simple GET
    status, body, elapsed = fetch("https://example.com/api", timeout=10)

    # With proxy
    status, body, elapsed = fetch("https://example.com/api", proxy="http://10.10.1.9:7890")

    # With headers + retry
    status, body, elapsed = fetch(url, headers={"Cookie": "..."}, retries=3)

    # POST JSON
    status, body, elapsed = fetch(url, data=json.dumps(payload).encode(),
                                  headers={"Content-Type": "application/json"})
"""
import logging
import socket
import ssl
import time
import urllib.parse

import urllib3

logger = logging.getLogger("pt-claw._http")

# Suppress urllib3 warning about unverified HTTPS (self-signed NAS certs etc.)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Global connection pool ─────────────────────────────────────
# One PoolManager shared by all scripts in the process. Connections are
# keyed by (scheme, host, port, proxy) and reused automatically.

_pool: urllib3.PoolManager | None = None
_proxy_pool: dict[str, urllib3.ProxyManager] = {}


def _get_pool(proxy: str | None = None) -> urllib3.PoolManager:
    """Return the global PoolManager (direct) or a ProxyManager (proxied)."""
    global _pool
    if proxy:
        if proxy not in _proxy_pool:
            _proxy_pool[proxy] = urllib3.ProxyManager(
                proxy,
                cert_reqs="CERT_NONE",
                timeout=urllib3.Timeout(connect=15, read=30),
                retries=False,  # we handle retries ourselves
                maxsize=5,
            )
        return _proxy_pool[proxy]
    if _pool is None:
        _pool = urllib3.PoolManager(
            cert_reqs="CERT_NONE",
            timeout=urllib3.Timeout(connect=15, read=30),
            retries=False,
            maxsize=5,
        )
    return _pool


# ── Proxy warmup ────────────────────────────────────────────────

_warmed_proxies: set[str] = set()


def warmup_proxy(proxy: str, timeout: float = 3.0) -> bool:
    """TCP-probe the proxy host to trigger ARP resolution and host wake-up.

    Sends a bare TCP SYN to the proxy address. If the host was asleep or
    the ARP cache was stale, this first connection (which may fail) triggers
    the network to resolve the MAC address. Subsequent requests then succeed.

    Returns True if the warmup succeeded (host reachable), False otherwise.
    Idempotent: a proxy is only warmed once per process lifetime.
    """
    if proxy in _warmed_proxies:
        return True

    parsed = urllib.parse.urlparse(proxy)
    host = parsed.hostname
    port = parsed.port
    if not host or not port:
        _warmed_proxies.add(proxy)
        return True

    # Try a quick TCP connect (may fail — that's fine, it still triggers ARP)
    for attempt in range(2):
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            _warmed_proxies.add(proxy)
            return True
        except (OSError, socket.timeout):
            if attempt == 0:
                # First failure: ARP may have been triggered, wait briefly
                time.sleep(0.5)
            else:
                logger.debug("Proxy warmup failed for %s (host may be offline)", proxy)
                # Still mark as warmed so we don't keep retrying
                _warmed_proxies.add(proxy)
                return False

    _warmed_proxies.add(proxy)
    return False


# ── Core fetch ──────────────────────────────────────────────────

_DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def fetch(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    proxy: str | None = None,
    timeout: float = 15.0,
    retries: int = 0,
    warmup: bool = False,
) -> tuple[int, str, float]:
    """HTTP request with connection pooling, optional retry and proxy warmup.

    Args:
        url: Full URL to request.
        method: HTTP method (GET, POST, etc).
        headers: Additional headers (User-Agent defaults if not set).
        data: Request body bytes.
        proxy: Proxy URL (e.g. "http://10.10.1.9:7890"). None for direct.
        timeout: Connect+read timeout in seconds.
        retries: Number of retries on transient errors (network, 5xx).
                 0 = no retry (default). Use 2-3 for proxy health checks.
        warmup: If True, warm up the proxy TCP connection before the real request.
                Recommended for cron-triggered proxy checks.

    Returns:
        (status_code, body_text, elapsed_ms)

    Raises:
        urllib3.exceptions.HTTPError on failure (after retries exhausted).
        OSError on network failure.
    """
    if proxy and warmup:
        warmup_proxy(proxy)

    merged_headers = {"User-Agent": _DEFAULT_UA}
    if headers:
        merged_headers.update(headers)

    # Convert timeout to urllib3 Timeout
    urllib3_timeout = urllib3.Timeout(connect=min(timeout, 10), read=timeout)

    pool = _get_pool(proxy)
    last_exc = None

    for attempt in range(1 + retries):
        try:
            t0 = time.time()
            resp = pool.urlopen(
                method=method,
                url=url,
                body=data,
                headers=merged_headers,
                timeout=urllib3_timeout,
                redirect=True,
                preload_content=False,
            )
            body = resp.read()
            elapsed = (time.time() - t0) * 1000

            # Decode body
            content_type = resp.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in content_type:
                import re
                m = re.search(r'charset=([\w-]+)', content_type)
                if m:
                    charset = m.group(1)

            try:
                body_text = body.decode(charset)
            except (UnicodeDecodeError, LookupError):
                body_text = body.decode("utf-8", errors="replace")

            return resp.status, body_text, elapsed

        except (urllib3.exceptions.MaxRetryError,
                urllib3.exceptions.NewConnectionError,
                urllib3.exceptions.TimeoutError,
                urllib3.exceptions.ProtocolError,
                OSError,
                socket.timeout) as exc:
            last_exc = exc
            if attempt < retries:
                wait = 1.5 ** attempt  # 1.5s, 2.25s, ...
                logger.debug("fetch retry %d/%d for %s: %s (waiting %.1fs)",
                             attempt + 1, retries, url, exc, wait)
                time.sleep(wait)
                # Re-warmup on retry — the host may still be waking
                if proxy and warmup:
                    _warmed_proxies.discard(proxy)
                    warmup_proxy(proxy)
            else:
                raise

    # Should not reach here, but just in case
    raise last_exc  # type: ignore[misc]


def fetch_raw(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    proxy: str | None = None,
    timeout: float = 15.0,
    retries: int = 0,
    warmup: bool = False,
) -> tuple[int, bytes, float]:
    """Like fetch() but returns raw bytes instead of decoded text.

    Use for binary content like .torrent files.
    Returns (status_code, body_bytes, elapsed_ms).
    """
    if proxy and warmup:
        warmup_proxy(proxy)

    merged_headers = {"User-Agent": _DEFAULT_UA}
    if headers:
        merged_headers.update(headers)

    urllib3_timeout = urllib3.Timeout(connect=min(timeout, 10), read=timeout)
    pool = _get_pool(proxy)
    last_exc = None

    for attempt in range(1 + retries):
        try:
            t0 = time.time()
            resp = pool.urlopen(
                method=method,
                url=url,
                body=data,
                headers=merged_headers,
                timeout=urllib3_timeout,
                redirect=True,
                preload_content=False,
            )
            body = resp.read()
            elapsed = (time.time() - t0) * 1000
            return resp.status, body, elapsed
        except (urllib3.exceptions.MaxRetryError,
                urllib3.exceptions.NewConnectionError,
                urllib3.exceptions.TimeoutError,
                urllib3.exceptions.ProtocolError,
                OSError,
                socket.timeout) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(1.5 ** attempt)
                if proxy and warmup:
                    _warmed_proxies.discard(proxy)
                    warmup_proxy(proxy)
            else:
                raise
    raise last_exc  # type: ignore[misc]


def fetch_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    proxy: str | None = None,
    timeout: float = 15.0,
    retries: int = 0,
) -> tuple[dict | list, float]:
    """Fetch URL and parse JSON response. Returns (parsed_json, elapsed_ms)."""
    import json
    merged = {"Accept": "application/json"}
    if headers:
        merged.update(headers)
    status, body, elapsed = fetch(url, headers=merged, data=data, proxy=proxy,
                                  timeout=timeout, retries=retries)
    return json.loads(body), elapsed


def reset_pool():
    """Clear all pooled connections. Useful after proxy changes."""
    global _pool, _proxy_pool
    if _pool is not None:
        _pool.clear()
    for pm in _proxy_pool.values():
        pm.clear()
    _proxy_pool.clear()
    _warmed_proxies.clear()
