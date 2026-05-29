#!/usr/bin/env python3
"""
Download history tracker — add, check, list entries in ~/.hermes/pt_downloaded.json.

Usage:
    python3 download_history.py add --code MIMK-267 --title "xxx" --source sukebei
    python3 download_history.py check --code MIMK-267          # returns json: {"exists": true/false}
    python3 download_history.py filter --stdin                  # reads codes from stdin, prints only new ones
    python3 download_history.py list                            # list all entries
"""

import json, os, sys, argparse, tempfile
from datetime import datetime

HISTORY_PATH = os.path.expanduser("~/.hermes/pt_downloaded.json")

DEFAULT_HISTORY = {
    "description": "记录所有已推送下载的内容，防止用户手动删除后被定时任务重复下载",
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


def cmd_add(code: str, title: str, source: str = "unknown") -> None:
    """Record a new download."""
    data = _load()
    # Don't duplicate
    existing = {i["code"] for i in data["items"]}
    if code in existing:
        print(json.dumps({"status": "skipped", "reason": f"{code} already in history"}))
        return
    data["items"].append({
        "code": code,
        "title": title,
        "added_at": datetime.now().isoformat(),
        "source": source,
        "status": "downloaded",
    })
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
        print(f"{item['code']:15s} | {item['added_at'][:19]} | {item['source']:10s} | {item['title'][:60]}")


def main():
    parser = argparse.ArgumentParser(description="PT download history tracker")
    sub = parser.add_subparsers(dest="cmd")

    p_add = sub.add_parser("add")
    p_add.add_argument("--code", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--source", default="unknown")

    p_check = sub.add_parser("check")
    p_check.add_argument("--code", required=True)

    p_filter = sub.add_parser("filter")
    p_filter.add_argument("--stdin", action="store_true")

    sub.add_parser("list")

    args = parser.parse_args()

    if args.cmd == "add":
        cmd_add(args.code, args.title, args.source)
    elif args.cmd == "check":
        cmd_check(args.code)
    elif args.cmd == "filter":
        cmd_filter()
    elif args.cmd == "list":
        cmd_list()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
