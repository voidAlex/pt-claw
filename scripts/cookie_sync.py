#!/usr/bin/env python3
"""
CookieCloud sync — pull browser cookies from CookieCloud and update secrets.env.

Usage:
    python3 cookie_sync.py                    # sync all PT sites
    python3 cookie_sync.py --dry-run          # preview only, don't write
    python3 cookie_sync.py --site btschool    # sync only one site

Requires CookieCloud env vars in secrets.env:
    COOKIE_CLOUD_HOST  — CookieCloud server URL (e.g. http://localhost:8088)
    COOKIE_CLOUD_UUID  — user UUID
    COOKIE_CLOUD_PASS  — encryption password

CookieCloud browser extension syncs cookies from browser to server.
This script pulls, decrypts, extracts PT site cookies, and writes to secrets.env.
"""
import base64, hashlib, json, os, re, sys

_skill_dir = os.path.dirname(os.path.abspath(__file__))

from _common import _env


def _decrypt_cookiecloud(uuid, encrypted, password):
    """Decrypt CookieCloud data. AES-CBC with EVP_BytesToKey (MD5).

    CookieCloud uses: key = MD5(uuid-password).hex()[:16] as passphrase,
    then CryptoJS.AES.encrypt which does EVP_BytesToKey on that passphrase.
    """
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend

    raw = base64.b64decode(encrypted)
    if raw[:8] != b"Salted__":
        raise ValueError("Invalid CookieCloud encrypted data")
    salt = raw[8:16]
    ciphertext = raw[16:]

    the_key = hashlib.md5((uuid + "-" + password).encode()).hexdigest()[:16]
    key_material = the_key.encode()
    dk = b""
    last = b""
    while len(dk) < 48:
        last = hashlib.md5(last + key_material + salt).digest()
        dk += last
    key, iv = dk[:32], dk[32:48]

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    pad_len = plaintext[-1]
    if pad_len > 16 or pad_len == 0:
        raise ValueError("Invalid PKCS7 padding")
    plaintext = plaintext[:-pad_len]

    return json.loads(plaintext)


SITE_DOMAINS = {
    "pttime": "pttime.org",
    "btschool": "pt.btschool.club",
    "carpt": "carpt.net",
    "hdfans": "hdfans.org",
    "1ptba": "1ptba.com",
    "soulvoice": "pt.soulvoice.club",
    "zmpt": "zmpt.cc",
    "ptskit": "www.ptskit.org",
    "pthome": "pthome.org",
    "hdsky": "hdsky.me",
    "hdhome": "hdhome.org",
    "audiences": "audiences.me",
    "keepfrds": "pt.keepfrds.com",
    "ttg": "totheglory.im",
}


def _extract_cookie_for_domain(cookie_data, domain):
    """Extract name=value pairs for a domain from CookieCloud cookie_data."""
    pairs = []
    for key, cookies in cookie_data.items():
        if not isinstance(cookies, list):
            continue
        for c in cookies:
            c_domain = c.get("domain", "").lstrip(".")
            if domain in c_domain or c_domain in domain:
                name = c.get("name", "")
                value = c.get("value", "")
                if name and value:
                    pairs.append(f"{name}={value}")
    return "; ".join(pairs)


def _update_secrets_env(updates, dry_run=False):
    """Update PT_COOKIE_* lines in secrets.env. Add missing ones at the end."""
    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            lines = f.readlines()

    updated_keys = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        for var_name, value in updates.items():
            if stripped.startswith(f"{var_name}="):
                lines[i] = f"{var_name}={value}\n"
                updated_keys.add(var_name)
                break

    for var_name, value in updates.items():
        if var_name not in updated_keys:
            lines.append(f"{var_name}={value}\n")

    if dry_run:
        print("  [dry-run] would update secrets.env:")
        for var_name, value in updates.items():
            print(f"    {var_name}={value[:40]}...")
        return

    with open(ENV_FILE, "w") as f:
        f.writelines(lines)
    print(f"  ✅ Updated {len(updates)} cookie(s) in secrets.env")


def main():
    import urllib.request, urllib.error

    dry_run = "--dry-run" in sys.argv
    only_site = None
    for i, arg in enumerate(sys.argv):
        if arg == "--site" and i + 1 < len(sys.argv):
            only_site = sys.argv[i + 1]

    host = _env("COOKIE_CLOUD_HOST", "")
    uuid = _env("COOKIE_CLOUD_UUID", "")
    password = _env("COOKIE_CLOUD_PASS", "")

    if not all([host, uuid, password]):
        print("❌ CookieCloud not configured. Set COOKIE_CLOUD_HOST/UUID/PASS in secrets.env")
        sys.exit(1)

    print(f"Fetching cookies from CookieCloud ({host})...")
    try:
        url = f"{host.rstrip('/')}/get/{uuid}"
        req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
        opener = urllib.request.build_opener()
        with opener.open(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"❌ Failed to fetch from CookieCloud: {e}")
        sys.exit(1)

    if not data or "encrypted" not in data:
        print("❌ No encrypted data in CookieCloud response")
        sys.exit(1)

    try:
        decrypted = _decrypt_cookiecloud(uuid, data["encrypted"], password)
    except ImportError:
        print("❌ Requires 'cryptography' package: pip install cryptography")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Decryption failed (wrong password?): {e}")
        sys.exit(1)

    cookie_data = decrypted.get("cookie_data", {})
    if not cookie_data:
        print("❌ No cookie_data in decrypted payload")
        sys.exit(1)

    print(f"Found {len(cookie_data)} domain(s) in CookieCloud")

    updates = {}
    for site_id, domain in SITE_DOMAINS.items():
        if only_site and site_id != only_site:
            continue
        cookie_str = _extract_cookie_for_domain(cookie_data, domain)
        if cookie_str:
            var_name = f"PT_COOKIE_{site_id.upper()}"
            updates[var_name] = cookie_str
            print(f"  📋 {site_id}: found cookie ({len(cookie_str)} chars)")
        else:
            print(f"  ⏭️  {site_id}: no cookie found for {domain}")

    if not updates:
        print("No PT site cookies found in CookieCloud")
        sys.exit(0)

    _update_secrets_env(updates, dry_run=dry_run)

    print("\n💡 Run `python3 scripts/connectivity_check.py` to verify updated cookies")


if __name__ == "__main__":
    main()
