#!/usr/bin/env python3
"""
Wishlist manager — add, remove, list entries in pt_wishlist.json.

Usage:
    python3 wishlist_manager.py add-actor --name "深田えいみ" --type adult_actress [--exclude-prefixes "FNS,ABC"] [--exclude-multi]
    python3 wishlist_manager.py remove-actor --name "深田えいみ"
    python3 wishlist_manager.py add-movie --title "镖人" [--year 2024] [--quality 4K] [--codec HEVC] [--note "note"]
    python3 wishlist_manager.py remove-movie --title "镖人"
    python3 wishlist_manager.py add-fanhao --code SSIS-448 [--note "收藏"]
    python3 wishlist_manager.py remove-fanhao --code SSIS-448
    python3 wishlist_manager.py list [--actors] [--movies] [--fanhao]
    python3 wishlist_manager.py json
"""

import json, os, sys, argparse, fcntl
from datetime import datetime, timezone

from _logger import get_logger
from _common import _env  # noqa: F401 — consistency import

log = get_logger("wishlist_manager")

WISHLIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pt_wishlist.json")
LOCK_PATH = WISHLIST_PATH + ".lock"

DEFAULT_WISHLIST = {
    "description": "关注列表 — 用户关注的影视、演员、番号，定时追剧用",
    "movies": [],
    "actors": [],
    "fanhao": [],
}


def _load() -> dict:
    if not os.path.exists(WISHLIST_PATH):
        return dict(DEFAULT_WISHLIST)
    try:
        with open(WISHLIST_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return dict(DEFAULT_WISHLIST)


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(WISHLIST_PATH), exist_ok=True)
    tmp = WISHLIST_PATH + ".tmp"
    with open(LOCK_PATH, "w") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, WISHLIST_PATH)
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


# ── actors ──────────────────────────────────────────────────────────────────

def cmd_add_actor(name: str, actor_type: str, exclude_prefixes: str = "", exclude_multi: bool = False) -> None:
    data = _load()
    for a in data.get("actors", []):
        if a["name"].lower() == name.lower():
            log.info("add_actor skipped name=%s reason=already_exists", name)
            print(json.dumps({"status": "skipped", "reason": f"actor '{name}' already exists"}))
            return
    entry = {"name": name, "type": actor_type, "exclude_prefixes": []}
    if exclude_prefixes:
        entry["exclude_prefixes"] = [p.strip() for p in exclude_prefixes.split(",") if p.strip()]
    if exclude_multi:
        entry["exclude_multi"] = True
    data.setdefault("actors", []).append(entry)
    _save(data)
    log.info("add_actor name=%s type=%s", name, actor_type)
    print(json.dumps({"status": "added", "name": name, "type": actor_type}))


def cmd_remove_actor(name: str) -> None:
    data = _load()
    actors = data.get("actors", [])
    before = len(actors)
    actors = [a for a in actors if a["name"].lower() != name.lower()]
    if len(actors) == before:
        log.info("remove_actor skipped name=%s reason=not_found", name)
        print(json.dumps({"status": "not_found", "reason": f"actor '{name}' not found"}))
        return
    data["actors"] = actors
    _save(data)
    log.info("remove_actor name=%s", name)
    print(json.dumps({"status": "removed", "name": name}))


# ── movies ──────────────────────────────────────────────────────────────────

def cmd_add_movie(title: str, year: int | None = None, quality: str = "",
                  codec: str = "", note: str = "") -> None:
    data = _load()
    for m in data.get("movies", []):
        if m["title"].lower() == title.lower():
            log.info("add_movie skipped title=%s reason=already_exists", title)
            print(json.dumps({"status": "skipped", "reason": f"movie '{title}' already exists"}))
            return
    entry = {"title": title, "year": year or None, "quality": quality or "4K", "codec": codec or "HEVC"}
    if note:
        entry["note"] = note
    data.setdefault("movies", []).append(entry)
    _save(data)
    log.info("add_movie title=%s", title)
    print(json.dumps({"status": "added", "title": title}))


def cmd_remove_movie(title: str) -> None:
    data = _load()
    movies = data.get("movies", [])
    before = len(movies)
    movies = [m for m in movies if m["title"].lower() != title.lower()]
    if len(movies) == before:
        log.info("remove_movie skipped title=%s reason=not_found", title)
        print(json.dumps({"status": "not_found", "reason": f"movie '{title}' not found"}))
        return
    data["movies"] = movies
    _save(data)
    log.info("remove_movie title=%s", title)
    print(json.dumps({"status": "removed", "title": title}))


# ── fanhao ──────────────────────────────────────────────────────────────────

def cmd_add_fanhao(code: str, note: str = "") -> None:
    data = _load()
    for f in data.get("fanhao", []):
        if isinstance(f, dict) and f.get("code", "").lower() == code.lower():
            log.info("add_fanhao skipped code=%s reason=already_exists", code)
            print(json.dumps({"status": "skipped", "reason": f"code '{code}' already exists"}))
            return
        elif isinstance(f, str) and f.lower() == code.lower():
            log.info("add_fanhao skipped code=%s reason=already_exists", code)
            print(json.dumps({"status": "skipped", "reason": f"code '{code}' already exists"}))
            return
    entry = {"code": code, "note": note, "added_at": datetime.now(timezone.utc).isoformat()}
    data.setdefault("fanhao", []).append(entry)
    _save(data)
    log.info("add_fanhao code=%s", code)
    print(json.dumps({"status": "added", "code": code}))


def cmd_remove_fanhao(code: str) -> None:
    data = _load()
    fanhao = data.get("fanhao", [])
    before = len(fanhao)
    fanhao = [f for f in fanhao
              if (f.get("code", "").lower() if isinstance(f, dict) else f.lower()) != code.lower()]
    if len(fanhao) == before:
        log.info("remove_fanhao skipped code=%s reason=not_found", code)
        print(json.dumps({"status": "not_found", "reason": f"code '{code}' not found"}))
        return
    data["fanhao"] = fanhao
    _save(data)
    log.info("remove_fanhao code=%s", code)
    print(json.dumps({"status": "removed", "code": code}))


# ── list / json ─────────────────────────────────────────────────────────────

def cmd_list(show_actors: bool = False, show_movies: bool = False, show_fanhao: bool = False) -> None:
    data = _load()
    # If no filter flags, show all
    show_all = not (show_actors or show_movies or show_fanhao)

    if show_all or show_actors:
        actors = data.get("actors", [])
        print(f"=== Actors ({len(actors)}) ===")
        for a in actors:
            exc = ",".join(a.get("exclude_prefixes", []))
            multi = " [exclude-multi]" if a.get("exclude_multi") else ""
            print(f"  {a['name']:20s} | {a.get('type', '?'):15s} | excl:{exc or 'none'}{multi}")

    if show_all or show_movies:
        movies = data.get("movies", [])
        print(f"=== Movies ({len(movies)}) ===")
        for m in movies:
            yr = str(m.get("year") or "?")
            q = m.get("quality", "")
            c = m.get("codec", "")
            n = m.get("note", "")
            print(f"  {m['title']:20s} | year:{yr:5s} | {q:3s} {c:4s} | {n}")

    if show_all or show_fanhao:
        fanhao = data.get("fanhao", [])
        print(f"=== Fanhao ({len(fanhao)}) ===")
        for f in fanhao:
            if isinstance(f, dict):
                note = f.get("note", "")
                at = f.get("added_at", "")[:16]
                print(f"  {f.get('code', '?'):15s} | {at:16s} | {note}")
            else:
                print(f"  {f}")

    log.info("list actors=%d movies=%d fanhao=%d",
             len(data.get("actors", [])), len(data.get("movies", [])), len(data.get("fanhao", [])))


def cmd_json() -> None:
    data = _load()
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ── main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PT wishlist manager")
    sub = parser.add_subparsers(dest="cmd")

    # add-actor
    p_aa = sub.add_parser("add-actor")
    p_aa.add_argument("--name", required=True)
    p_aa.add_argument("--type", required=True, dest="actor_type")
    p_aa.add_argument("--exclude-prefixes", default="")
    p_aa.add_argument("--exclude-multi", action="store_true")

    # remove-actor
    p_ra = sub.add_parser("remove-actor")
    p_ra.add_argument("--name", required=True)

    # add-movie
    p_am = sub.add_parser("add-movie")
    p_am.add_argument("--title", required=True)
    p_am.add_argument("--year", type=int, default=None)
    p_am.add_argument("--quality", default="")
    p_am.add_argument("--codec", default="")
    p_am.add_argument("--note", default="")

    # remove-movie
    p_rm = sub.add_parser("remove-movie")
    p_rm.add_argument("--title", required=True)

    # add-fanhao
    p_af = sub.add_parser("add-fanhao")
    p_af.add_argument("--code", required=True)
    p_af.add_argument("--note", default="")

    # remove-fanhao
    p_rf = sub.add_parser("remove-fanhao")
    p_rf.add_argument("--code", required=True)

    # list
    p_list = sub.add_parser("list")
    p_list.add_argument("--actors", action="store_true")
    p_list.add_argument("--movies", action="store_true")
    p_list.add_argument("--fanhao", action="store_true")

    # json
    sub.add_parser("json")

    args = parser.parse_args()

    if args.cmd == "add-actor":
        cmd_add_actor(args.name, args.actor_type, args.exclude_prefixes, args.exclude_multi)
    elif args.cmd == "remove-actor":
        cmd_remove_actor(args.name)
    elif args.cmd == "add-movie":
        cmd_add_movie(args.title, args.year, args.quality, args.codec, args.note)
    elif args.cmd == "remove-movie":
        cmd_remove_movie(args.title)
    elif args.cmd == "add-fanhao":
        cmd_add_fanhao(args.code, args.note)
    elif args.cmd == "remove-fanhao":
        cmd_remove_fanhao(args.code)
    elif args.cmd == "list":
        cmd_list(args.actors, args.movies, args.fanhao)
    elif args.cmd == "json":
        cmd_json()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
