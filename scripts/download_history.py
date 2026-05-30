#!/usr/bin/env python3
"""
Download history tracker — add, check, list, cross-seed entries in pt_downloaded.json.

Usage:
    python3 download_history.py add --code MIMK-267 --title "xxx" --source sukebei
    python3 download_history.py add --code MIMK-267 --title "xxx" --source pttime --source-site mteam --cross-seed-from "MIMK-267@mteam"
    python3 download_history.py check --code MIMK-267          # returns json: {"exists": true/false}
    python3 download_history.py filter --stdin                  # reads codes from stdin, prints only new ones
    python3 download_history.py list                            # list all entries
    python3 download_history.py cross-seed --code MIMK-267 --title "xxx" --source pttime --original-source mteam
"""

import json, os, sys, argparse
from datetime import datetime, timezone

HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pt_downloaded.json")

DEFAULT_HISTORY = {
    "description": "下载历史 — 防止用户手动删除后定时任务重复下载",
    "items": []
}


def _load() -> dict:
    if not os.path.exists(HISTORY_PATH):
        return dict(DEFAULT_HISTORY)
    with open(HISTORY_PATH) as f:
        return json.load(f)


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    tmp = HISTORY_PATH + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_PATH)


def cmd_add(code: str, title: str, source: str = "unknown",
            source_site: str = "", cross_seed_from: str = "") -> None:
    """Record a new download."""
    data = _load()
    existing = {i["code"] for i in data["items"]}
    if code in existing:
        print(json.dumps({"status": "skipped", "reason": f"{code} already in history"}))
        return
    item = {
        "code": code,
        "title": title,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "status": "downloaded",
    }
    if source_site:
        item["source_site"] = source_site
    if cross_seed_from:
        item["cross_seed_from"] = cross_seed_from
    data["items"].append(item)
    _save(data)
    print(json.dumps({"status": "added", "code": code}))


def cmd_check(code: str) -> None:
    """Check if a code exists in history."""
    data = _load()
    codes = {i["code"] for i in data["items"]}
    print(json.dumps({"exists": code in codes, "code": code}))


def cmd_filter() -> None:
    """Read codes from stdin, print only those NOT in history."""
    data = _load()
    known = {i["code"] for i in data["items"]}
    for line in sys.stdin:
        code = line.strip()
        if code and code not in known:
            print(code)


def cmd_list() -> None:
    """List all entries."""
    data = _load()
    for item in data["items"]:
        status = item.get("status", "downloaded")
        if status == "cross_seeded":
            status = f"cross_seeded from {item.get('source_site', '?')}"
        print(f"{item['code']:15s} | {item['added_at'][:19]} | {item['source']:10s} | {item['title'][:60]:60s} | {status}")


def main():
    parser = argparse.ArgumentParser(description="PT download history tracker")
    sub = parser.add_subparsers(dest="cmd")

    p_add = sub.add_parser("add")
    p_add.add_argument("--code", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--source", default="unknown")
    p_add.add_argument("--source-site", default="")
    p_add.add_argument("--cross-seed-from", default="")

    p_check = sub.add_parser("check")
    p_check.add_argument("--code", required=True)

    p_filter = sub.add_parser("filter")
    p_filter.add_argument("--stdin", action="store_true")

    sub.add_parser("list")

    p_cross = sub.add_parser("cross-seed")
    p_cross.add_argument("--code", required=True)
    p_cross.add_argument("--title", required=True)
    p_cross.add_argument("--source", required=True)
    p_cross.add_argument("--original-source", required=True)

    args = parser.parse_args()

    if args.cmd == "add":
        cmd_add(args.code, args.title, args.source, args.source_site, args.cross_seed_from)
    elif args.cmd == "check":
        cmd_check(args.code)
    elif args.cmd == "filter":
        cmd_filter()
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "cross-seed":
        data = _load()
        existing = {i["code"] for i in data["items"]}
        if args.code in existing:
            print(json.dumps({"status": "skipped", "reason": f"{args.code} already in history"}))
            return
        data["items"].append({
            "code": args.code,
            "title": args.title,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "source": args.source,
            "source_site": args.original_source,
            "cross_seed_from": f"{args.code}@{args.original_source}",
            "status": "cross_seeded",
        })
        _save(data)
        print(json.dumps({"status": "cross_seeded", "code": args.code, "from": args.original_source}))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
