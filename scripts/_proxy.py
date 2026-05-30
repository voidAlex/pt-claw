"""
Proxy compatibility layer.

urllib.request.ProxyHandler has compatibility issues with certain proxy types,
causing "No route to host" errors. This module provides a context manager
that uses environment variables instead, which urllib picks up automatically
via its default ProxyHandler.

Usage:
    from _proxy import using_proxy

    with using_proxy(proxy_url):
        opener = urllib.request.build_opener()
        resp = opener.open(req, timeout=15)

    with using_proxy(None):
        opener = urllib.request.build_opener()
        resp = opener.open(req, timeout=15)  # direct, no proxy
"""
import contextlib
import os

_PROXY_KEYS = ('http_proxy', 'https_proxy')


@contextlib.contextmanager
def using_proxy(proxy_url):
    """Temporarily set proxy env vars for urllib requests.

    Thread-safe: each opener captures proxy settings at build_opener() time,
    so concurrent threads with different proxy needs work correctly.

    Args:
        proxy_url: Proxy URL (e.g. "http://10.10.1.9:7890") or None to clear.
    """
    saved = {}
    for k in _PROXY_KEYS:
        saved[k] = os.environ.get(k)

    if proxy_url:
        os.environ['http_proxy'] = proxy_url
        os.environ['https_proxy'] = proxy_url
    else:
        for k in _PROXY_KEYS:
            os.environ.pop(k, None)

    try:
        yield
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
