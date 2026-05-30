#!/usr/bin/env python3
"""
Add torrents to qBittorrent via Web API with file selection support.

Usage:
    python3 qb_add.py "magnet:?xt=urn:btih:ABCDEF..." --tags sukebei
    python3 qb_add.py "magnet:?xt=urn:btih:ABCDEF..." --tags sukebei --max-video
    python3 qb_add.py --stdin                              # read from stdin (JSON)
    python3 qb_add.py --from-search "query" --index 0      # search then add by index

Public magnet file selection (two-step):
    python3 qb_add.py "magnet:?..." --tags sukebei --list-files
    python3 qb_add.py --select-files <hash> --keep 0,3,5
"""

import json, os, re, sys, time, urllib.request, urllib.parse, urllib.error
from http.cookiejar import CookieJar

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "secrets.env")
_env_cache = None


def _load_env_file():
    global _env_cache
    if _env_cache is not None:
        return
    _env_cache = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    _env_cache[k.strip()] = v.strip()


def _env(key, default=""):
    val = os.environ.get(key, "")
    if not val:
        _load_env_file()
        val = _env_cache.get(key, default)
    return val


# ── QBittorrent session (reusable) ────────────────────────────
_qb_opener = None
_qb_url = None


def _get_opener():
    """Return a logged-in qB opener, reusing the session cookie."""
    global _qb_opener, _qb_url
    if _qb_opener is not None:
        return _qb_opener

    _qb_url = _env("QBITTORRENT_URL", "")
    qb_user = _env("QBITTORRENT_USER", "")
    qb_pass = _env("QBITTORRENT_PASS", "")

    cj = CookieJar()
    _qb_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    _qb_opener.addheaders = [("User-Agent", "Hermes/1.0")]
    login_data = urllib.parse.urlencode({"username": qb_user, "password": qb_pass}).encode()
    try:
        _qb_opener.open(f"{_qb_url}/api/v2/auth/login", login_data, timeout=10)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError("Login failed — check QBITTORRENT_USER/PASS in secrets.env")
        raise
    return _qb_opener


def qb_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Make an authenticated request to qBittorrent Web API."""
    opener = _get_opener()
    full_url = f"{_qb_url}{endpoint}"
    if method == "POST" and data:
        req = urllib.request.Request(full_url,
                                     data=urllib.parse.urlencode(data).encode(),
                                     method=method)
    else:
        req = urllib.request.Request(full_url, method=method)
    try:
        with opener.open(req, timeout=30) as resp:
            raw = resp.read()
            if not raw.strip():
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                text = raw.decode("utf-8", errors="replace").strip()
                return {"raw": text}
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e}"}


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


def _select_main_video(info_hash: str, code: str = "", timeout: int = 30) -> dict:
    """For a paused torrent, identify the main video file, skip everything else, then resume.

    Heuristic (in priority order):
    1. Files containing the search code (e.g. "MIMK-267") → largest among them
    2. Largest video file, EXCLUDING those with ad/sample keywords
    3. If no video found at all, keep the single largest file
    """
    import os

    AD_KEYWORDS = ["广告", "ad", "sample", "preview", "trailer", "promo",
                   "推广", "宣传", "预告", "试看", "预览", "sample", "demo"]

    # Wait for metadata
    deadline = time.time() + timeout
    files = []
    while time.time() < deadline:
        files = qb_request(f"/api/v2/torrents/files?hash={info_hash}")
        if isinstance(files, list) and len(files) > 0:
            break
        if "error" in files:
            time.sleep(2)
            continue
        time.sleep(2)

    if not isinstance(files, list) or len(files) == 0:
        qb_request("/api/v2/torrents/resume", method="POST", data={"hashes": info_hash})
        return {"video_file": None, "skipped_count": 0, "kept_count": 0, "warning": "metadata timeout"}

    # Annotate with index
    for i, f in enumerate(files):
        f["_index"] = i

    VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".wmv", ".mov", ".ts", ".m2ts", ".webm", ".flv"}
    video_files = [f for f in files if os.path.splitext(f.get("name", "").lower())[1] in VIDEO_EXTS]
    non_video = [f for f in files if f not in video_files]

    def _is_ad(f):
        name = f.get("name", "").lower()
        return any(kw in name for kw in AD_KEYWORDS)

    main = None

    # Priority 1: file matching the code
    if code and video_files:
        code_matches = [f for f in video_files if code.lower() in f.get("name", "").lower()]
        if code_matches:
            main = max(code_matches, key=lambda f: f.get("size", 0))

    # Priority 2: largest non-ad video
    if main is None and video_files:
        clean = [f for f in video_files if not _is_ad(f)]
        if clean:
            main = max(clean, key=lambda f: f.get("size", 0))
        else:
            # All videos look like ads — still pick largest but warn
            main = max(video_files, key=lambda f: f.get("size", 0))

    # Priority 3: largest file of any kind
    if main is None:
        main = max(files, key=lambda f: f.get("size", 0))

    # Also keep matching subtitle files
    keep_indices = {main["_index"]}
    if main:
        base_name = os.path.splitext(main["name"])[0]
        for f in non_video:
            fname = f.get("name", "")
            _, fext = os.path.splitext(fname.lower())
            if fext in {".srt", ".ass", ".ssa", ".sub", ".idx"}:
                sub_base = os.path.splitext(fname)[0]
                if sub_base.startswith(base_name) or base_name in sub_base:
                    keep_indices.add(f["_index"])

    # Skip all non-kept files
    skip_indices = [i for i in range(len(files)) if i not in keep_indices]
    if skip_indices:
        qb_request("/api/v2/torrents/filePrio", method="POST",
                   data={"hash": info_hash,
                         "id": "|".join(str(i) for i in skip_indices),
                         "priority": "0"})

    qb_request("/api/v2/torrents/resume", method="POST", data={"hashes": info_hash})

    return {
        "video_file": main.get("name") if main else None,
        "video_size_mb": round(main.get("size", 0) / 1048576, 1) if main else 0,
        "skipped_count": len(skip_indices),
        "kept_count": len(keep_indices),
    }


def list_files(info_hash: str, timeout: int = 60) -> dict:
    """List all files in a paused torrent. Used with --list-files for public magnets.

    Returns JSON with file list: index, name, size, extension, is_video, is_subtitle.
    Torrent stays paused after listing — caller must use --select-files or --resume.
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
    for i, f in enumerate(files):
        name = f.get("name", "")
        _, ext = os.path.splitext(name.lower())
        size_bytes = f.get("size", 0)
        result.append({
            "index": i,
            "name": name,
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / 1048576, 1),
            "ext": ext,
            "is_video": ext in VIDEO_EXTS,
            "is_subtitle": ext in SUB_EXTS,
        })

    torrent_info = qb_request(f"/api/v2/torrents/info?hashes={info_hash}")
    torrent_name = ""
    if isinstance(torrent_info, list) and torrent_info:
        torrent_name = torrent_info[0].get("name", "")

    return {
        "info_hash": info_hash,
        "torrent_name": torrent_name,
        "total_files": len(result),
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

    If max_video=True, torrent is added paused, non-video files are skipped,
    then resumed.
    """
    data = {"urls": url_or_magnet}
    if save_path:
        data["savepath"] = save_path
    if category:
        data["category"] = category
    if max_video:
        data["paused"] = "true"

    result = qb_request("/api/v2/torrents/add", method="POST", data=data)
    if "error" in result:
        return result

    msg = f"Added: {url_or_magnet[:80]}..."
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

    # ── Video-only filtering ──────────────────────────────
    if max_video and info_hash:
        try:
            filt = _select_main_video(info_hash, code=code)
            if filt.get("video_file"):
                result["max_video"] = filt
            elif filt.get("warning"):
                result["video_warning"] = filt["warning"]
        except Exception as e:
            result["video_error"] = str(e)
            # Resume anyway so torrent isn't stuck
            qb_request("/api/v2/torrents/resume", method="POST", data={"hashes": info_hash})

    # ── Apply tags ──────────────────────────────────────────
    if tags and isinstance(tags, list) and len(tags) > 0 and info_hash:
        tag_result = add_tags(info_hash, tags)
        if "error" not in tag_result:
            result["tags_added"] = tags
        else:
            result["tag_error"] = tag_result["error"]

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

    for i, a in enumerate(sys.argv[1:]):
        if a == "--path" and i + 1 < len(sys.argv) - 1:
            save_path = sys.argv[i + 2]
        elif a == "--category" and i + 1 < len(sys.argv) - 1:
            category = sys.argv[i + 2]
        elif a == "--tags" and i + 1 < len(sys.argv) - 1:
            tags = [t.strip() for t in sys.argv[i + 2].split(",") if t.strip()]

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

        result = list_files(info_hash)
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
        data = json.loads(r.stdout)
        items = data.get("results", [])
        if idx >= len(items):
            print(json.dumps({"error": f"Index {idx} out of range ({len(items)} results)"}))
            sys.exit(1)
        url = items[idx]["download_url"]
        result = add_torrent(url, save_path=save_path, category=category,
                           tags=tags, max_video=max_video)
        result["added_title"] = items[idx]["title"]
        print(json.dumps(result, ensure_ascii=False))
        return

    # ── Direct URL/magnet ────────────────────────────────────
    if not args:
        print(json.dumps({"error": "No URL/magnet provided"}))
        sys.exit(1)

    url = args[0]
    result = add_torrent(url, save_path=save_path, category=category,
                       tags=tags, max_video=max_video)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
