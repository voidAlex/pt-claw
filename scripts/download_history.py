#!/usr/bin/env python3
"""
Download history tracker — add, check, complete, list, cross-seed entries in pt_downloaded.json.

Usage:
    python3 download_history.py add --code MIMK-267 --title "xxx" --source sukebei
    python3 download_history.py add --code MIMK-267 --title "xxx" --source pttime --source-site mteam --cross-seed-from "MIMK-267@mteam"
    python3 download_history.py check --code MIMK-267          # returns json: {"exists": true/false}
    python3 download_history.py complete --code MIMK-267       # mark as completed (cron calls this)
    python3 download_history.py complete-by-hash --hash abc123 --name "ROYD-318"  # match by hash/name
    python3 download_history.py filter --stdin                  # reads codes from stdin, prints only new ones
    python3 download_history.py list                            # list all entries
    python3 download_history.py cross-seed --code MIMK-267 --title "xxx" --source pttime --original-source mteam
"""

import json, os, sys, argparse
from datetime import datetime, timezone

from _logger import get_logger

log = get_logger("download_history")

HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pt_downloaded.json")

DEFAULT_HISTORY = {
    "description": "下载历史 — 防止用户手动删除后定时任务重复下载",
    "items": []
}


def _load() -> dict:
    if not os.path.exists(HISTORY_PATH):
        return dict(DEFAULT_HISTORY)
    try:
        with open(HISTORY_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        # Corrupted file — reset to default
        return dict(DEFAULT_HISTORY)


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    tmp = HISTORY_PATH + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_PATH)


def _find_item(data: dict, code: str) -> tuple[dict | None, int]:
    for i, item in enumerate(data["items"]):
        if item.get("code") == code:
            return item, i
    return None, -1


def cmd_add(code: str, title: str, source: str = "unknown",
            source_site: str = "", cross_seed_from: str = "") -> None:
    """Record a new download."""
    data = _load()
    existing = {i["code"] for i in data["items"]}
    if code in existing:
        log.info("add skipped code=%s reason=already_exists", code)
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
    log.info("added code=%s source=%s", code, source)
    print(json.dumps({"status": "added", "code": code}))


def cmd_complete(code: str) -> None:
    """Mark a download as completed (called by cron when torrent finishes)."""
    data = _load()
    item, idx = _find_item(data, code)
    if item is None:
        log.info("complete skipped code=%s reason=not_found", code)
        print(json.dumps({"status": "not_found", "code": code}))
        return
    if "completed_at" in item:
        log.info("complete skipped code=%s reason=already_completed", code)
        print(json.dumps({"status": "already_completed", "code": code}))
        return
    item["completed_at"] = datetime.now(timezone.utc).isoformat()
    item["status"] = "completed"
    data["items"][idx] = item
    _save(data)
    log.info("completed code=%s", code)
    print(json.dumps({"status": "completed", "code": code}))


def cmd_complete_by_hash(info_hash: str, name: str = "") -> None:
    """Mark download completed by matching torrent hash against item code/name."""
    data = _load()
    h = info_hash.lower()
    updated = 0
    for item in data["items"]:
        if item.get("status") == "completed":
            continue
        code = item.get("code", "").lower()
        title = item.get("title", "").lower()
        if name and name.lower().startswith(code):
            item["completed_at"] = datetime.now(timezone.utc).isoformat()
            item["status"] = "completed"
            item["completed_hash"] = h
            updated += 1
    if updated:
        _save(data)
    log.info("complete_by_hash hash=%s updated=%d", h, updated)
    print(json.dumps({"status": "updated", "count": updated, "hash": h}))


def cmd_check(code: str) -> None:
    """Check if a code exists in history."""
    data = _load()
    codes = {i["code"] for i in data["items"]}
    exists = code in codes
    log.info("check code=%s exists=%s", code, exists)
    print(json.dumps({"exists": exists, "code": code}))


def cmd_filter() -> None:
    """Read codes from stdin, print only those NOT in history."""
    data = _load()
    known = {i["code"] for i in data["items"]}
    passed = 0
    for line in sys.stdin:
        code = line.strip()
        if code and code not in known:
            print(code)
            passed += 1
    log.info("filter total_known=%d passed=%d", len(known), passed)


def cmd_list() -> None:
    """List all entries."""
    data = _load()
    for item in data["items"]:
        status = item.get("status", "downloaded")
        completed = item.get("completed_at", "")
        comp_str = f" ✓{completed[:16]}" if completed else ""
        if status == "cross_seeded":
            status = f"cross_seeded from {item.get('source_site', '?')}"
        print(f"{item['code']:15s} | {item['added_at'][:19]} | {item['source']:10s} | {item['title'][:50]:50s} | {status}{comp_str}")


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

    p_complete = sub.add_parser("complete")
    p_complete.add_argument("--code", required=True)

    p_complete_hash = sub.add_parser("complete-by-hash")
    p_complete_hash.add_argument("--hash", required=True)
    p_complete_hash.add_argument("--name", default="")

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
    elif args.cmd == "complete":
        cmd_complete(args.code)
    elif args.cmd == "complete-by-hash":
        cmd_complete_by_hash(args.hash, args.name)
    elif args.cmd == "filter":
        cmd_filter()
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "cross-seed":
        data = _load()
        existing = {i["code"] for i in data["items"]}
        if args.code in existing:
            log.info("cross_seed skipped code=%s reason=already_exists", args.code)
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
        log.info("cross_seed code=%s from=%s", args.code, args.original_source)
        print(json.dumps({"status": "cross_seeded", "code": args.code, "from": args.original_source}))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
