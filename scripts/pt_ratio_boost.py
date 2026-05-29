#!/usr/bin/env python3
"""
PT ratio booster — auto-download freeleech torrents, delete after aging out.

Usage:
    python3 pt_ratio_boost.py run                    # One-shot run
    python3 pt_ratio_boost.py cleanup                # Delete aged torrents only
    python3 pt_ratio_boost.py status                 # Show current boost tasks

Config: ~/.hermes/pt_boost.json
{
    "enabled": false,
    "sites": ["mteam"],
    "qb_url": "http://<host>:<port>",
    "qb_user": "<username>",
    "qb_pass": "<password>",
    "boost_category": "boost",
    "boost_save_path": "/downloads/pt-boost",
    "max_seed_days": 7,
    "max_torrents": 20,
    "freeleech_only": true,
    "min_size_gb": 5,
    "max_size_gb": 200,
    "min_seeders": 5
}
"""

import json, os, re, sys, time, urllib.request, urllib.parse, http.cookiejar, subprocess

MAX_DELETE_PER_RUN = 50

# Import backup module
_skill_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _skill_dir)
from qb_backup import backup_from_torrents
from datetime import datetime, timedelta

CONFIG_PATH = os.path.expanduser("~/.hermes/pt_boost.json")
TRACKER_PATH = os.path.expanduser("~/.hermes/pt_boost_tracker.json")

DEFAULT_CONFIG = {
    "enabled": False,
    "sites": [],
    "qb_url": "",
    "qb_user": "",
    "qb_pass": "",
    "boost_category": "boost",
    "boost_save_path": "",
    "max_seed_days": 7,
    "max_torrents": 20,
    "freeleech_only": True,
    "min_size_gb": 5,
    "max_size_gb": 200,
    "min_seeders": 5,
}


# ── Config ────────────────────────────────────────────────────
def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


# ── qBittorrent ───────────────────────────────────────────────
class QBit:
    def __init__(self, url: str, user: str, password: str):
        self.url = url.rstrip("/")
        self.jar = None
        self._login(user, password)

    def _login(self, user: str, password: str):
        """Authenticate and store cookies."""
        self.jar = {}
        data = urllib.parse.urlencode({"username": user, "password": password}).encode()
        req = urllib.request.Request(f"{self.url}/api/v2/auth/login", data=data)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                for h in resp.headers.get_all("Set-Cookie", []):
                    if "SID=" in h:
                        self.jar["SID"] = h.split("SID=")[1].split(";")[0]
        except Exception as e:
            raise RuntimeError(f"qBittorrent login failed: {e}")

    def _get(self, endpoint: str) -> dict | list:
        url = f"{self.url}/api/v2/{endpoint}"
        req = urllib.request.Request(url)
        if "SID" in self.jar:
            req.add_header("Cookie", f"SID={self.jar['SID']}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())

    def _post(self, endpoint: str, data: dict) -> str:
        url = f"{self.url}/api/v2/{endpoint}"
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=body)
        if "SID" in self.jar:
            req.add_header("Cookie", f"SID={self.jar['SID']}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode()

    def list_torrents(self, category: str = "") -> list[dict]:
        endpoint = "torrents/info"
        if category:
            endpoint += f"?category={urllib.parse.quote(category)}"
        return self._get(endpoint)

    def add_torrent(self, url_or_magnet: str, category: str = "", save_path: str = "") -> bool:
        data = {"urls": url_or_magnet}
        if category:
            data["category"] = category
        if save_path:
            data["savepath"] = save_path
        resp = self._post("torrents/add", data)
        return resp.strip() == "Ok."

    def delete_torrents(self, hashes: list[str], delete_files: bool = True):
        data = {"hashes": "|".join(hashes), "deleteFiles": str(delete_files).lower()}
        self._post("torrents/delete", data)

    def categories(self) -> dict:
        return self._get("torrents/categories")


# ── PT search (delegates to mteam_api / pt_search) ────────────
def search_freeleech(site: str, cfg: dict) -> list[dict]:
    """Search a PT site for freeleech torrents matching boost criteria."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results = []

    if site == "mteam":
        api_key = os.environ.get("MTEAM_API_KEY", "")
        if not api_key:
            return [{"error": "MTEAM_API_KEY not set", "source": "mteam"}]
        mteam_script = os.path.join(script_dir, "mteam_api.py")
        r = subprocess.run(
            ["python3", mteam_script, "search", "1080p", "--limit", "50"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "MTEAM_API_KEY": api_key},
        )
        try:
            items = json.loads(r.stdout)
        except json.JSONDecodeError:
            return [{"error": "mteam_api parse error", "source": "mteam"}]

        for item in items:
            if "error" in item:
                continue
            torrent_id = item.get("id", "")
            if not torrent_id or not re.match(r'^[\w-]+$', str(torrent_id)):
                continue
            # Freeleech only
            if cfg["freeleech_only"] and item.get("promo", "") not in ("Free", "50%", "30%"):
                continue
            # Size filter
            size_gb = item.get("size_bytes", 0) / (1024**3)
            if size_gb < cfg["min_size_gb"] or size_gb > cfg["max_size_gb"]:
                continue
            # Seeders
            if item.get("seeders", 0) < cfg["min_seeders"]:
                continue
            # Generate download URL
            dl_r = subprocess.run(
                ["python3", mteam_script, "download", str(torrent_id)],
                capture_output=True, text=True, timeout=15,
                env={**os.environ, "MTEAM_API_KEY": api_key},
            )
            try:
                dl = json.loads(dl_r.stdout)
                item["download_url"] = dl.get("download_url", "")
            except json.JSONDecodeError:
                item["download_url"] = ""
            results.append(item)

    return results


# ── Age-out cleanup ───────────────────────────────────────────
def cleanup_aged(cfg: dict, qb: QBit, dry_run: bool = False) -> list[dict]:
    """Delete boost torrents that have been seeding longer than max_seed_days.
    
    Safety: dry_run=True shows preview only. dry_run=False actually deletes after backup.
    """
    torrents = qb.list_torrents(cfg["boost_category"])
    now = time.time()
    max_age = cfg["max_seed_days"] * 86400
    to_delete = []

    for t in torrents:
        added_on = t.get("added_on", 0)
        age = now - added_on
        if age > max_age:
            to_delete.append(t)

    if len(to_delete) > MAX_DELETE_PER_RUN:
        print(json.dumps({
            "error": "SAFEGUARD: delete cap exceeded",
            "to_delete": len(to_delete),
            "max_allowed": MAX_DELETE_PER_RUN,
            "message": f"待删 {len(to_delete)} 个超过上限 {MAX_DELETE_PER_RUN}，中止。请人工确认后分批删除。",
        }, ensure_ascii=False, indent=2))
        return []

    preview = {
        "check_mode": True,
        "category": cfg["boost_category"],
        "max_seed_days": cfg["max_seed_days"],
        "total_in_category": len(torrents),
        "would_delete": len(to_delete),
        "would_delete_list": [{
            "hash": t["hash"][:12],
            "name": t["name"][:80],
            "age_days": round((now - t.get("added_on", 0)) / 86400, 1),
            "size": _fmt_size(t.get("size", 0)),
            "state": t.get("state", ""),
        } for t in to_delete],
    }

    if dry_run:
        preview["tip"] = "确认删除请运行: python3 pt_ratio_boost.py cleanup"
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return to_delete

    if to_delete:
        hashes = [t["hash"] for t in to_delete]
        backup_from_torrents(to_delete, reason="boost_aged")
        qb.delete_torrents(hashes, delete_files=True)
        print(f"🧹 清理 {len(to_delete)} 个过期种子 (>{cfg['max_seed_days']}天)")
    
    return to_delete


# ── Add new boost torrents ────────────────────────────────────
def add_new(cfg: dict, qb: QBit) -> list[dict]:
    """Search for and add new freeleech torrents."""
    current = qb.list_torrents(cfg["boost_category"])
    current_count = len(current)

    # How many slots available
    slots = cfg["max_torrents"] - current_count
    if slots <= 0:
        print(f"📦 已达上限 {cfg['max_torrents']}，跳过新增")
        return []

    added = []
    for site in cfg["sites"]:
        if len(added) >= slots:
            break

        results = search_freeleech(site, cfg)
        for item in results:
            if len(added) >= slots:
                break
            dl_url = item.get("download_url", "")
            if not dl_url:
                continue
            ok = qb.add_torrent(dl_url, cfg["boost_category"], cfg["boost_save_path"])
            if ok:
                added.append(item)
                print(f"➕ {item['title'][:60]} ({item.get('size','?')})")

    return added


# ── Status ────────────────────────────────────────────────────
def show_status(cfg: dict, qb: QBit):
    torrents = qb.list_torrents(cfg["boost_category"])
    now = time.time()

    total_upload = sum(t.get("uploaded", 0) for t in torrents)
    total_download = sum(t.get("downloaded", 0) for t in torrents)
    ratio = total_upload / total_download if total_download > 0 else float("inf")

    print(f"\n📊 刷流状态 ({cfg['boost_category']})")
    print(f"   当前种子: {len(torrents)}/{cfg['max_torrents']}")
    print(f"   总上传: {_fmt_size(total_upload)}")
    print(f"   总下载: {_fmt_size(total_download)}")
    print(f"   分享率: {ratio:.2f}")
    print(f"   最大做种: {cfg['max_seed_days']} 天")
    print(f"   仅免费: {'是' if cfg['freeleech_only'] else '否'}")
    print()

    if torrents:
        torrents.sort(key=lambda t: t.get("added_on", 0))
        for t in torrents[:10]:
            age_days = (now - t.get("added_on", 0)) / 86400
            print(f"   {'🧹' if age_days > cfg['max_seed_days'] else '🔄'} "
                  f"{age_days:4.0f}d | {t['name'][:50]}")


# ── Main ──────────────────────────────────────────────────────
def _fmt_size(b: int) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"


def main():
    cfg = load_config()

    if not cfg.get("enabled"):
        print("⚠️ 刷流未启用。编辑 ~/.hermes/pt_boost.json 设置 enabled: true")
        sys.exit(0)

    if not all([cfg.get("qb_url"), cfg.get("qb_user"), cfg.get("qb_pass")]):
        print("❌ qBittorrent 配置不完整，检查 pt_boost.json")
        sys.exit(1)

    if not cfg.get("boost_save_path"):
        print("❌ 未设置 boost_save_path")
        sys.exit(1)

    try:
        qb = QBit(cfg["qb_url"], cfg["qb_user"], cfg["qb_pass"])
    except Exception as e:
        print(f"❌ 连接 qBittorrent 失败: {e}")
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    dry_run = "--check" in sys.argv

    if cmd == "cleanup":
        cleanup_aged(cfg, qb, dry_run=dry_run)
    elif cmd == "status":
        show_status(cfg, qb)
    elif cmd == "run":
        if dry_run:
            print(json.dumps({
                "check_mode": True,
                "message": "run mode: preview only (--check enabled)",
            }, ensure_ascii=False, indent=2))
            cleanup_aged(cfg, qb, dry_run=True)
            torrents = qb.list_torrents(cfg["boost_category"])
            stalled = [t for t in torrents if t.get("state", "") == "stalledDL"]
            now_check = time.time()
            stalled_dead = []
            for t in stalled:
                age = now_check - t.get("added_on", 0)
                if age > 86400 * cfg["max_seed_days"]:
                    stalled_dead.append(t)
            if stalled_dead:
                print(json.dumps({
                    "check_mode": True,
                    "stalled_dead": [{
                        "hash": t["hash"][:12],
                        "name": t["name"][:80],
                        "age_days": round((now_check - t.get("added_on", 0)) / 86400, 1),
                    } for t in stalled_dead],
                    "tip": "These stalled dead torrents would be deleted (with files).",
                }, ensure_ascii=False, indent=2))
            show_status(cfg, qb)
        else:
            deleted = cleanup_aged(cfg, qb, dry_run=False)

            torrents = qb.list_torrents(cfg["boost_category"])
            stalled = [t for t in torrents if t.get("state", "") == "stalledDL"]
            for t in stalled:
                age = time.time() - t.get("added_on", 0)
                if age > 86400 * cfg["max_seed_days"]:
                    backup_from_torrents([t], reason="boost_dead")
                    qb.delete_torrents([t["hash"]], delete_files=True)

            added = add_new(cfg, qb)
            show_status(cfg, qb)

    else:
        print(f"Usage: pt_ratio_boost.py [run|cleanup|status]")


if __name__ == "__main__":
    main()
