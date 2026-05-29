#!/bin/bash
# pt-claw proxy wrapper — only applies proxy to this subprocess.
# Reads PT_PROXY from ~/.hermes/.env or environment.
# Usage: bash scripts/with_proxy.sh python3 scripts/pt_search.py "query"

if [ -z "$PT_PROXY" ] && [ -f ~/.hermes/.env ]; then
    PT_PROXY=$(grep -oP '^PT_PROXY=\K.*' ~/.hermes/.env 2>/dev/null || true)
fi
if [ -z "$PT_PROXY" ]; then
    echo "ERROR: PT_PROXY not set in env or ~/.hermes/.env" >&2
    exit 1
fi

export HTTP_PROXY="$PT_PROXY"
export HTTPS_PROXY="$PT_PROXY"
exec "$@"
