#!/usr/bin/env python3
"""
Add torrents to qBittorrent via Web API with site tag and video-only support.

Usage:
    python3 qb_add.py "magnet:?xt=urn:btih:ABCDEF..." --tags sukebei --video-only
    python3 qb_add.py "https://example.com/file.torrent" --tags mteam
    python3 qb_add.py --stdin                              # read from stdin (JSON)
    python3 qb_add.py --from-search "query" --index 0      # search then add by index

The --stdin mode expects JSON with "download_url"/"magnet" and optional "tags",
"video_only", "save_path", "category" fields.
"""

import json, os, re, sys, time, urllib.request, urllib.parse, urllib.error
from http.cookiejar import CookieJar


def _env(key, default=""):
    return os.environ.get(key, default)


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
    login_data = urllib.parse.urlencode({"username": qb_user, "password": qb_pass}).encode()
    try:
        _qb_opener.open(f"{_qb_url}/api/v2/auth/login", login_data, timeout=10)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError("Login failed — check QBITTORRENT_USER/PASS in .env")
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


def add_torrent(url_or_magnet: str, save_path: str = None,
                category: str = None, tags: list[str] = None,
                video_only: bool = False, code: str = "") -> dict:
    """Add a torrent by magnet link or URL, then apply tags.

    If video_only=True, torrent is added paused, non-video files are skipped,
    then resumed.
    """
    data = {"urls": url_or_magnet}
    if save_path:
        data["savepath"] = save_path
    if category:
        data["category"] = category
    if video_only:
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
    if video_only and info_hash:
        try:
            filt = _select_main_video(info_hash, code=code)
            if filt.get("video_file"):
                result["video_only"] = filt
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
    video_only = "--video-only" in sys.argv

    for i, a in enumerate(sys.argv[1:]):
        if a == "--path" and i + 1 < len(sys.argv) - 1:
            save_path = sys.argv[i + 2]
        elif a == "--category" and i + 1 < len(sys.argv) - 1:
            category = sys.argv[i + 2]
        elif a == "--tags" and i + 1 < len(sys.argv) - 1:
            tags = [t.strip() for t in sys.argv[i + 2].split(",") if t.strip()]

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
        vo = data.get("video_only", video_only)
        code = data.get("code", "")
        if isinstance(tgs, str):
            tgs = [t.strip() for t in tgs.split(",") if t.strip()]

        result = add_torrent(url, save_path=path, category=cat, tags=tgs, video_only=vo, code=code)
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
        results = json.loads(r.stdout)
        if idx >= len(results):
            print(json.dumps({"error": f"Index {idx} out of range ({len(results)} results)"}))
            sys.exit(1)
        url = results[idx]["download_url"]
        result = add_torrent(url, save_path=save_path, category=category,
                           tags=tags, video_only=video_only)
        result["added_title"] = results[idx]["title"]
        print(json.dumps(result, ensure_ascii=False))
        return

    # ── Direct URL/magnet ────────────────────────────────────
    if not args:
        print(json.dumps({"error": "No URL/magnet provided"}))
        sys.exit(1)

    url = args[0]
    result = add_torrent(url, save_path=save_path, category=category,
                       tags=tags, video_only=video_only)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
