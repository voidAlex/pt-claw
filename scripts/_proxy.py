"""
Proxy compatibility layer (legacy — kept for backward compatibility).

New code should use ``from _http import fetch`` instead, which provides
connection pooling, retry, and proxy warmup out of the box.

This module is retained because some scripts still use the env-var based
proxy approach with urllib.request.  It will be removed once all scripts
have been migrated to ``_http.fetch()``.
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
