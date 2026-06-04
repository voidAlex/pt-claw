#!/usr/bin/env python3
"""
Add torrents to qBittorrent via Web API with file selection support.

Usage:
    python3 qb_add.py "magnet:?xt=urn:btih:ABCDEF..." --tags sukebei
    python3 qb_add.py "magnet:?xt=urn:btih:ABCDEF..." --tags sukebei --max-video --code MIDE-990
    python3 qb_add.py --stdin                              # read from stdin (JSON)
    python3 qb_add.py --from-search "query" --index 0      # search then add by index

Local .torrent file upload:
    python3 qb_add.py --file /tmp/xxx.torrent --category movies --tags mteam

Tag/category management on existing torrents:
    python3 qb_add.py --retag <hash> --tags tag1,tag2
    python3 qb_add.py --recat <hash> --category movies

Public magnet file selection (two-step):
    python3 qb_add.py "magnet:?..." --tags sukebei --list-files
    python3 qb_add.py --select-files <hash> --keep 0,3,5
"""

import json, os, re, sys, time, uuid, urllib.request, urllib.parse

from _common import _env
from _logger import get_logger
from _qb_session import get_session as _get_session, qb_request as _qb_api_request, reset as _reset_session

log = get_logger("qb_add")


# Re-export for backward compat with scripts that import from qb_add
_qb_url = None


def _get_opener():
    opener, url = _get_session()
    global _qb_url
    _qb_url = url
    return opener


def qb_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    return _qb_api_request(endpoint, method, data)


def _extract_hash_from_magnet(magnet: str) -> str | None:
    """Extract info hash from magnet URI."""
    m = re.search(r'btih:([a-fA-F0-9]{40})', magnet)
    return m.group(1).upper() if m else None


def _find_recent_hashes(pattern: str, limit: int = 10, retries: int = 8, delay: float = 1.0) -> list[str]:
    """Poll qB for recently added torrents matching a name pattern."""
    for _ in range(retries):
        info = qb_request(f"/api/v2/torrents/info?sort=added_on&reverse=true&limit={limit}")
        if "error" in info:
            time.sleep(delay)
            continue
        hashes = []
        for t in info:
            if pattern.lower() in t.get("name", "").lower():
                hashes.append(t.get("hash", ""))
        if hashes:
            return hashes
        time.sleep(delay)
    return []


def add_tags(hashes: str | list[str], tags: str | list[str]) -> dict:
    """Add tags to torrents in qBittorrent."""
    if isinstance(hashes, list):
        hashes = "|".join(hashes)
    if isinstance(tags, list):
        tags = ",".join(tags)
    return qb_request("/api/v2/torrents/addTags", method="POST",
                       data={"hashes": hashes, "tags": tags})


def list_files(info_hash: str, code: str = "", timeout: int = 60) -> dict:
    """List all files in a paused torrent. Returns flat list + auto-recommendation.

    The 'recommended' field: largest video file + code-matching extras
    (subtitles, covers with matching base name). Agent uses this as a hint
    but makes the final decision via --select-files --keep.
    """
    VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".wmv", ".mov", ".ts", ".m2ts", ".webm", ".flv"}
    SUB_EXTS = {".srt", ".ass", ".ssa", ".sub", ".idx"}

    deadline = time.time() + timeout
    files = []
    while time.time() < deadline:
        files = qb_request(f"/api/v2/torrents/files?hash={info_hash}")
        if isinstance(files, list) and len(files) > 0 and files[0].get("size", 0) > 0:
            break
        if isinstance(files, dict) and "error" in files:
            return files
        time.sleep(2)

    if not isinstance(files, list) or len(files) == 0:
        return {"error": "metadata timeout — torrent may have no peers"}

    result = []
    video_entries = []
    for i, f in enumerate(files):
        name = f.get("name", "")
        _, ext = os.path.splitext(name.lower())
        size_bytes = f.get("size", 0)
        entry = {
            "index": i,
            "name": name,
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / 1048576, 1),
            "ext": ext,
            "is_video": ext in VIDEO_EXTS,
            "is_subtitle": ext in SUB_EXTS,
        }
        result.append(entry)
        if entry["is_video"]:
            video_entries.append(entry)

    recommended_main = None
    recommended_extras = []
    if video_entries:
        main = max(video_entries, key=lambda f: f["size_bytes"])
        main_base = os.path.splitext(main["name"])[0].lower()
        recommended_main = {"index": main["index"], "name": main["name"], "size_mb": main["size_mb"]}
        for e in result:
            if e["index"] == main["index"]:
                continue
            e_base = os.path.splitext(e["name"])[0].lower()
            e_name = e["name"].lower()
            if e_base.startswith(main_base) or main_base in e_base or main_base in e_name:
                if e["is_subtitle"] or e["ext"] in {".jpg", ".png", ".jpeg"}:
                    recommended_extras.append({"index": e["index"], "name": e["name"], "size_mb": e["size_mb"]})
        code_lower = code.lower()
        if code_lower:
            for e in result:
                if e["index"] == main["index"]:
                    continue
                if code_lower in e["name"].lower():
                    already = any(r["index"] == e["index"] for r in recommended_extras)
                    if not already:
                        recommended_extras.append({"index": e["index"], "name": e["name"], "size_mb": e["size_mb"]})

    torrent_info = qb_request(f"/api/v2/torrents/info?hashes={info_hash}")
    torrent_name = ""
    if isinstance(torrent_info, list) and torrent_info:
        torrent_name = torrent_info[0].get("name", "")

    return {
        "info_hash": info_hash,
        "torrent_name": torrent_name,
        "total_files": len(result),
        "recommended": {
            "main": recommended_main,
            "extras": recommended_extras,
        },
        "files": result,
        "next_step": f"Select files to keep, then: python3 qb_add.py --select-files {info_hash} --keep 0,3,5",
    }


def select_files(info_hash: str, keep_indices: list[int]) -> dict:
    """Skip all files NOT in keep_indices, then resume the torrent.

    Used after --list-files: user confirms which files to download.
    """
    files = qb_request(f"/api/v2/torrents/files?hash={info_hash}")
    if not isinstance(files, list) or len(files) == 0:
        return {"error": f"No files found for hash {info_hash}"}

    total = len(files)
    keep_set = set(keep_indices)
    skip_indices = [i for i in range(total) if i not in keep_set]

    kept_names = []
    for i in keep_indices:
        if 0 <= i < total:
            kept_names.append(files[i].get("name", f"file_{i}"))

    if skip_indices:
        qb_request("/api/v2/torrents/filePrio", method="POST",
                   data={"hash": info_hash,
                         "id": "|".join(str(i) for i in skip_indices),
                         "priority": "0"})

    qb_request("/api/v2/torrents/resume", method="POST", data={"hashes": info_hash})

    return {
        "info_hash": info_hash,
        "kept_files": len(keep_indices),
        "skipped_files": len(skip_indices),
        "kept_names": kept_names,
        "status": "resumed",
    }


def add_torrent(url_or_magnet: str, save_path: str = None,
                category: str = None, tags: list[str] = None,
                max_video: bool = False, code: str = "") -> dict:
    """Add a torrent by magnet link or URL, then apply tags.

    If max_video=True, torrent is added paused, then the largest video
    + code-matching extras are auto-selected before resuming.
    """
    import urllib.parse as _up
    _logged_url = url_or_magnet
    try:
        _parsed = _up.urlparse(url_or_magnet)
        if _parsed.query:
            _params = _up.parse_qs(_parsed.query, keep_blank_values=True)
            _filtered_parts = []
            for _k, _v_list in _params.items():
                if _k.lower() in ("passkey", "sign", "token"):
                    continue
                _filtered_parts.append(f"{_k}={_v_list[0]}")
            _new_qs = "&".join(_filtered_parts)
            _logged_url = _up.urlunparse(_parsed._replace(query=_new_qs, fragment=""))
    except Exception:
        pass
    data = {"urls": url_or_magnet}
    if save_path:
        data["savepath"] = save_path
    if category:
        data["category"] = category
    if tags and isinstance(tags, list) and len(tags) > 0:
        data["tags"] = ",".join(tags)
    if max_video:
        data["paused"] = "true"

    result = qb_request("/api/v2/torrents/add", method="POST", data=data)
    if "error" in result:
        log.error("add torrent failed url=%s error=%s", _logged_url[:80], result["error"])
        return result

    log.info("adding torrent url=%s category=%s tags=%s max_video=%s", _logged_url[:80], category, tags, max_video)
    msg = f"Added: {_logged_url[:80]}..."
    result = {"success": True, "message": msg}

    # ── Get info hash ──────────────────────────────────────
    info_hash = _extract_hash_from_magnet(url_or_magnet)
    if not info_hash:
        # Torrent URL — poll
        url_basename = url_or_magnet.rsplit("/", 1)[-1].rsplit("?", 1)[0]
        pattern = url_basename.rsplit(".", 1)[0] if "." in url_basename else url_basename
        if len(pattern) > 3:
            found = _find_recent_hashes(pattern, retries=12, delay=1.5)
            info_hash = found[0] if found else None

    if info_hash:
        result["info_hash"] = info_hash
        log.info("torrent identified hash=%s", info_hash)

    # ── Max-video: use list_files recommendation to auto-select ──
    if max_video and info_hash:
        log.info("max-video hash=%s code=%s", info_hash, code)
        try:
            listing = list_files(info_hash, code=code, timeout=60)
            rec = listing.get("recommended", {})
            main = rec.get("main", {})
            extras = rec.get("extras", [])
            keep = [main["index"]] if main else []
            keep += [e["index"] for e in extras]
            if keep:
                sel_result = select_files(info_hash, keep)
                result["max_video"] = {
                    "selected_main": main.get("name"),
                    "selected_extras": [e["name"] for e in extras],
                    "skipped": sel_result.get("skipped_files", 0),
                }
                log.info("max-video auto-selected main=%s extras=%d skipped=%d",
                         main.get("name"), len(extras), sel_result.get("skipped_files", 0))
            else:
                qb_request("/api/v2/torrents/resume", method="POST", data={"hashes": info_hash})
                result["max_video"] = {"warning": "no video files found, resumed all"}
        except Exception as e:
            result["video_error"] = str(e)
            log.error("max-video failed hash=%s error=%s", info_hash, e)

    # ── Apply tags ──────────────────────────────────────────
    if tags and isinstance(tags, list) and len(tags) > 0 and info_hash:
        tag_result = add_tags(info_hash, tags)
        if "error" not in tag_result:
            result["tags_added"] = tags
            log.info("tags applied hash=%s tags=%s", info_hash, tags)
        else:
            result["tag_error"] = tag_result["error"]
            log.warning("tag failed hash=%s tags=%s error=%s", info_hash, tags, tag_result["error"])

    return result


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    # ── Parse flags ──────────────────────────────────────────
    save_path = None
    category = None
    tags = []
    max_video = "--max-video" in sys.argv
    code = ""

    for i, a in enumerate(sys.argv[1:]):
        if a == "--path" and i + 1 < len(sys.argv) - 1:
            save_path = sys.argv[i + 2]
        elif a == "--category" and i + 1 < len(sys.argv) - 1:
            category = sys.argv[i + 2]
        elif a == "--tags" and i + 1 < len(sys.argv) - 1:
            tags = [t.strip() for t in sys.argv[i + 2].split(",") if t.strip()]
        elif a == "--code" and i + 1 < len(sys.argv) - 1:
            code = sys.argv[i + 2]

    # ── --retag mode (add tags to existing torrents) ──────────
    if "--retag" in sys.argv:
        if not tags:
            print(json.dumps({"error": "--retag requires --tags <tag1,tag2>"}))
            sys.exit(1)
        hashes = []
        retag_idx = sys.argv.index("--retag")
        if retag_idx + 1 < len(sys.argv) and not sys.argv[retag_idx + 1].startswith("-"):
            hashes = [sys.argv[retag_idx + 1]]
        else:
            for a in sys.argv:
                if a.startswith("--hash="):
                    hashes = [a.split("=", 1)[1]]
                    break
            if not hashes:
                hashes_str = ""
                for a in sys.argv:
                    if a.startswith("--hashes="):
                        hashes_str = a.split("=", 1)[1]
                        break
                if hashes_str:
                    hashes = [h.strip() for h in hashes_str.split(",") if h.strip()]
        if not hashes:
            print(json.dumps({"error": "--retag requires a hash argument: --retag <hash> or --hash=<hash>"}))
            sys.exit(1)
        log.info("retagging hashes=%s tags=%s", hashes, tags)
        result = add_tags(hashes, tags)
        if "error" not in result:
            print(json.dumps({"status": "tagged", "hashes": hashes if isinstance(hashes, list) else [hashes], "tags": tags}))
        else:
            print(json.dumps({"error": result["error"]}))
        return

    # ── --recat mode (set category on existing torrents) ────────
    if "--recat" in sys.argv:
        if not category:
            print(json.dumps({"error": "--recat requires --category <category>"}))
            sys.exit(1)
        hashes = []
        recat_idx = sys.argv.index("--recat")
        if recat_idx + 1 < len(sys.argv) and not sys.argv[recat_idx + 1].startswith("-"):
            hashes = [sys.argv[recat_idx + 1]]
        else:
            for a in sys.argv:
                if a.startswith("--hash="):
                    hashes = [a.split("=", 1)[1]]
                    break
            if not hashes:
                hashes_str = ""
                for a in sys.argv:
                    if a.startswith("--hashes="):
                        hashes_str = a.split("=", 1)[1]
                        break
                if hashes_str:
                    hashes = [h.strip() for h in hashes_str.split(",") if h.strip()]
        if not hashes:
            print(json.dumps({"error": "--recat requires a hash argument: --recat <hash> or --hash=<hash>"}))
            sys.exit(1)
        log.info("recatting hashes=%s category=%s", hashes, category)
        hashes_param = "|".join(hashes) if isinstance(hashes, list) else hashes
        result = qb_request("/api/v2/torrents/setCategory", method="POST",
                            data={"hashes": hashes_param, "category": category})
        if "error" not in result:
            print(json.dumps({"status": "recatted", "hashes": hashes if isinstance(hashes, list) else [hashes], "category": category}))
        else:
            print(json.dumps({"error": result["error"]}))
        return

    # ── --file mode (upload local .torrent via multipart) ─────────
    if "--file" in sys.argv:
        file_idx = sys.argv.index("--file")
        file_path = sys.argv[file_idx + 1] if file_idx + 1 < len(sys.argv) and not sys.argv[file_idx + 1].startswith("-") else ""
        if not file_path:
            print(json.dumps({"error": "--file requires a path argument: --file /tmp/xxx.torrent"}))
            sys.exit(1)
        if not os.path.isfile(file_path):
            print(json.dumps({"error": "file not found: %s" % file_path}))
            sys.exit(1)
        try:
            with open(file_path, "rb") as f:
                torrent_data = f.read()
        except OSError as e:
            print(json.dumps({"error": "cannot read file: %s" % e}))
            sys.exit(1)
        if not torrent_data:
            print(json.dumps({"error": "file is empty: %s" % file_path}))
            sys.exit(1)
        if torrent_data[0:1] != b"d":
            print(json.dumps({"error": "not a valid .torrent file (missing bencode dict marker): %s" % file_path}))
            sys.exit(1)

        opener = _get_opener()
        boundary = "----QbAdd%s" % uuid.uuid4().hex[:16]
        filename = os.path.basename(file_path)
        if not filename.endswith(".torrent"):
            filename += ".torrent"

        parts = []
        parts.append(("--%s\r\n"
                       'Content-Disposition: form-data; name="torrents"; '
                       'filename="%s"\r\n'
                       "Content-Type: application/x-bittorrent\r\n\r\n" % (boundary, filename)).encode())

        field_parts = []
        if save_path:
            field_parts.append("--%s\r\n"
                               'Content-Disposition: form-data; name="savepath"\r\n\r\n'
                               "%s\r\n" % (boundary, save_path))
        if category:
            field_parts.append("--%s\r\n"
                               'Content-Disposition: form-data; name="category"\r\n\r\n'
                               "%s\r\n" % (boundary, category))
        if tags:
            tag_str = ",".join(tags)
            field_parts.append("--%s\r\n"
                               'Content-Disposition: form-data; name="tags"\r\n\r\n'
                               "%s\r\n" % (boundary, tag_str))

        body = b"".join(parts) + torrent_data + b"\r\n"
        for fp in field_parts:
            body += fp.encode()
        body += ("--%s--\r\n" % boundary).encode()

        req = urllib.request.Request(
            "%s/api/v2/torrents/add" % _qb_url,
            data=body,
            headers={
                "Content-Type": "multipart/form-data; boundary=%s" % boundary,
            },
            method="POST",
        )
        try:
            with opener.open(req, timeout=30) as resp:
                resp.read()
            log.info("file upload ok file=%s category=%s tags=%s", file_path, category, tags)
            print(json.dumps({"success": True, "message": "Uploaded: %s" % filename,
                              "file": file_path, "category": category, "tags": tags}))
        except Exception as e:
            log.error("file upload failed file=%s error=%s", file_path, e)
            print(json.dumps({"error": "upload failed: %s" % e}))
            sys.exit(1)
        return

    # ── --select-files mode (step 2: apply selection + resume) ──
    if "--select-files" in sys.argv:
        sf_idx = sys.argv.index("--select-files")
        info_hash = sys.argv[sf_idx + 1] if sf_idx + 1 < len(sys.argv) else ""
        keep_str = ""
        for a in sys.argv:
            if a.startswith("--keep="):
                keep_str = a.split("=", 1)[1]
        if not info_hash:
            print(json.dumps({"error": "--select-files requires <hash> and --keep=0,3,5"}))
            sys.exit(1)
        keep_indices = [int(x.strip()) for x in keep_str.split(",") if x.strip().isdigit()]
        if not keep_indices:
            print(json.dumps({"error": "--keep= required (e.g. --keep=0,3,5)"}))
            sys.exit(1)
        result = select_files(info_hash, keep_indices)
        print(json.dumps(result, ensure_ascii=False))
        return

    # ── --list-files mode (step 1: add paused + list files) ─────
    if "--list-files" in sys.argv:
        if not args:
            print(json.dumps({"error": "--list-files requires a magnet/URL argument"}))
            sys.exit(1)
        url = args[0]
        data = {"urls": url, "paused": "true"}
        if save_path:
            data["savepath"] = save_path
        if category:
            data["category"] = category
        add_result = qb_request("/api/v2/torrents/add", method="POST", data=data)
        if "error" in add_result:
            print(json.dumps(add_result))
            sys.exit(1)

        info_hash = _extract_hash_from_magnet(url)
        if not info_hash:
            url_basename = url.rsplit("/", 1)[-1].rsplit("?", 1)[0]
            pattern = url_basename.rsplit(".", 1)[0] if "." in url_basename else url_basename
            if len(pattern) > 3:
                found = _find_recent_hashes(pattern, retries=15, delay=2)
                info_hash = found[0] if found else None
        if not info_hash:
            print(json.dumps({"error": "Could not determine info hash after adding"}))
            sys.exit(1)

        if tags:
            add_tags(info_hash, tags)

        result = list_files(info_hash, code=code)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # ── stdin mode ───────────────────────────────────────────
    if "--stdin" in sys.argv:
        raw = sys.stdin.read()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"download_url": raw.strip()}

        url = data.get("download_url") or data.get("magnet") or data.get("link", "")
        if not url:
            print(json.dumps({"error": "No download_url/magnet found in stdin input"}))
            sys.exit(1)

        path = data.get("save_path", save_path)
        cat = data.get("category", category)
        tgs = data.get("tags", tags)
        vo = data.get("max_video") or data.get("video_only", max_video)
        code = data.get("code", "")
        if isinstance(tgs, str):
            tgs = [t.strip() for t in tgs.split(",") if t.strip()]

        result = add_torrent(url, save_path=path, category=cat, tags=tgs, max_video=vo, code=code)
        print(json.dumps(result, ensure_ascii=False))
        return

    # ── --from-search mode ───────────────────────────────────
    if "--from-search" in sys.argv:
        index_vals = [a.replace("--index=", "") for a in sys.argv if a.startswith("--index=")]
        if not index_vals:
            print(json.dumps({"error": "--from-search requires --index=N"}))
            sys.exit(1)
        idx = int(index_vals[0])
        import subprocess
        search_dir = os.path.dirname(os.path.abspath(__file__))
        search_script = os.path.join(search_dir, "pt_search.py")
        query = " ".join(args)
        r = subprocess.run(["python3", search_script, query],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not r.stdout.strip():
            print(json.dumps({"error": f"Search failed: {r.stderr[:200]}"}))
            sys.exit(1)
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Search returned invalid JSON"}))
            sys.exit(1)
        items = data.get("results", [])
        if idx >= len(items):
            print(json.dumps({"error": f"Index {idx} out of range ({len(items)} results)"}))
            sys.exit(1)
        url = items[idx]["download_url"]
        result = add_torrent(url, save_path=save_path, category=category,
                           tags=tags, max_video=max_video, code=code)
        result["added_title"] = items[idx]["title"]
        print(json.dumps(result, ensure_ascii=False))
        return

    # ── Direct URL/magnet ────────────────────────────────────
    if not args:
        print(json.dumps({"error": "No URL/magnet provided"}))
        sys.exit(1)

    url = args[0]
    result = add_torrent(url, save_path=save_path, category=category,
                       tags=tags, max_video=max_video, code=code)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
