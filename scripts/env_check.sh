#!/bin/bash
# PT Downloader — environment prerequisite check
# Run before any PT/Jellyfin operation to verify all required env vars are present.
# Sources secrets.env and reports which keys are missing.
# Exit 0 if all required keys found, 1 if any missing.

ENV_FILE="$(dirname "$(dirname "$(readlink -f "$0")")")/secrets.env"
# Safe env parser — handles '=' in cookie values (unlike bash source which breaks on ';')
# SKILL.md #25: never `source secrets.env` directly
if [[ -f "$ENV_FILE" ]]; then
    while IFS= read -r line; do
        line="${line%%#*}"
        [[ -z "$line" || "$line" != *=* ]] && continue
        key="${line%%=*}"
        val="${line#*=}"
        export "${key}=${val}"
    done < "$ENV_FILE" 2>/dev/null
fi

MISSING=0
check() {
    local name="$1" desc="$2"
    if [[ -z "${!name}" ]]; then
        echo "  ✗ $name — $desc"
        MISSING=$((MISSING + 1))
    else
        echo "  ✓ $name (set)"
    fi
}

echo "=== qBittorrent ==="
check QBITTORRENT_URL  "qBittorrent base URL"
check QBITTORRENT_USER "qBittorrent username"
check QBITTORRENT_PASS "qBittorrent password"

echo "=== M-Team (optional) ==="
if [[ -n "${MTEAM_API_KEY}" ]]; then
    echo "  ✓ MTEAM_API_KEY (set, ${#MTEAM_API_KEY} chars)"
else
    echo "  ℹ MTEAM_API_KEY — not set (M-Team API search disabled)"
fi

echo "=== Jellyfin (adult) ==="
check JELLYFIN1_URL  "Adult Jellyfin URL (e.g. JF adult address)"
check JELLYFIN1_API_KEY "Adult Jellyfin API key"

echo "=== Jellyfin (movie/TV) ==="
check JELLYFIN2_URL  "Movie/TV Jellyfin URL (e.g. JF TV address)"
check JELLYFIN2_API_KEY "Movie/TV Jellyfin API key"

echo "=== Proxy ==="
if [[ -n "${PT_PROXY}" ]]; then
    echo "  ✓ PT_PROXY set"
else
    echo "  ⚠ PT_PROXY not set — sites like zmpt.cc may timeout"
fi

echo "=== PT Cookies ==="
for site in PTTIME BTSCHOOL CARPT HDFANS 1PTBA SOULVOICE ZMPT; do
    var="PT_COOKIE_${site}"
    if [[ -n "${!var}" ]]; then
        _cookie_val="${!var}"
        echo "  ✓ PT_COOKIE_${site} (set, ${#_cookie_val} chars)"
    else
        echo "  ⚠ PT_COOKIE_${site} — missing"
    fi
done

echo "=== CookieCloud (optional) ==="
if [[ -n "${COOKIE_CLOUD_HOST}" ]]; then
    echo "  ✓ COOKIE_CLOUD_HOST (set)"
    check COOKIE_CLOUD_UUID "CookieCloud UUID"
    check COOKIE_CLOUD_PASS "CookieCloud password"
else
    echo "  ℹ Not configured (manual cookie management)"
fi

echo "=== javbus-api (optional) ==="
if [[ -n "${JAVBUS_API_URL}" ]]; then
    echo "  ✓ JAVBUS_API_URL ($JAVBUS_API_URL)"
else
    echo "  ℹ Not configured (raw JavBus scraping)"
fi

echo ""
if [[ $MISSING -eq 0 ]]; then
    echo "All required keys present."
    exit 0
else
    echo "${MISSING} config(s) missing — add them to secrets.env"
    exit 1
fi
