#!/usr/bin/env python3
"""
PT ratio booster — auto-download freeleech torrents, delete after aging out.

Usage:
    python3 scripts/pt_ratio_boost.py run                    # One-shot: cleanup + add new
    python3 scripts/pt_ratio_boost.py cleanup                # Delete aged torrents only
    python3 scripts/pt_ratio_boost.py status                 # Show current boost tasks

Config: <skill-dir>/pt_boost.json (template: templates/pt_boost.example.json)
"""

import json, os, re, sys, time, urllib.request, urllib.parse, subprocess

from _common import _env, _fmt_size, _parse_size
from _qb_session import get_session, qb_request as _qb_api_req

MAX_DELETE_PER_RUN = 50

_skill_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _skill_dir)
from qb_snapshot import backup_from_torrents

CONFIG_PATH = os.path.join(_skill_dir, "..", "pt_boost.json")


DEFAULT_GLOBAL = {
    "boost_category": "boost",
    "boost_save_path": "",
    "max_seed_days": 7,
    "max_torrents": 20,
    "dead_seed_hours": 48,
    "delete_files": True,
}

DEFAULT_SITE = {
    "search_keyword": "",
    "freeleech_only": True,
    "exclude_hr": True,
    "sort_by": "seeders",
    "sort_order": "desc",
    "min_size_gb": 5,
    "max_size_gb": 200,
    "min_seeders": 5,
    "max_results": 50,
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {"enabled": False, "global": dict(DEFAULT_GLOBAL), "sites": {}, "per_run_add_limit": 5}
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    g = cfg.setdefault("global", {})
    for k, v in DEFAULT_GLOBAL.items():
        g.setdefault(k, v)
    sites = cfg.setdefault("sites", {})
    for site_id, site_cfg in sites.items():
        for k, v in DEFAULT_SITE.items():
            site_cfg.setdefault(k, v)
    cfg.setdefault("per_run_add_limit", 5)
    return cfg


class QBit:
    def __init__(self, url: str, user: str, password: str):
        self.opener, self.url = get_session()

    def list_torrents(self, category: str = "") -> list[dict]:
        endpoint = "torrents/info"
        if category:
            endpoint += f"?category={urllib.parse.quote(category)}"
        result = _qb_api_req(f"/{endpoint}")
        return result if isinstance(result, list) else []

    def add_torrent(self, url_or_magnet: str, category: str = "", save_path: str = "") -> bool:
        data = {"urls": url_or_magnet}
        if category:
            data["category"] = category
        if save_path:
            data["savepath"] = save_path
        result = _qb_api_req("/torrents/add", method="POST", data=data)
        return isinstance(result, dict) and "error" not in result

    def delete_torrents(self, hashes: list[str], delete_files: bool = True):
        data = {"hashes": "|".join(hashes), "deleteFiles": str(delete_files).lower()}
        _qb_api_req("/torrents/delete", method="POST", data=data)


def search_freeleech(site_id: str, site_cfg: dict, global_cfg: dict) -> list[dict]:
    """Search a PT site for freeleech torrents matching boost criteria."""
    results = []

    if site_id == "mteam":
        api_key = _env("MTEAM_API_KEY", "")
        if not api_key:
            return [{"error": "MTEAM_API_KEY not set", "source": "mteam"}]
        mteam_script = os.path.join(_skill_dir, "mteam_api.py")
        keyword = site_cfg.get("search_keyword", "") or ""
        max_results = site_cfg.get("max_results", 50)
        r = subprocess.run(
            ["python3", mteam_script, "search", keyword or " ", "--limit", str(max_results)],
            capture_output=True, text=True, timeout=60,
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
            if site_cfg.get("freeleech_only") and item.get("promo", "") not in ("Free",):
                continue
            if site_cfg.get("exclude_hr", True) and "HR" in item.get("title", ""):
                continue
            size_gb = item.get("size_bytes", 0) / (1024**3)
            if size_gb < site_cfg.get("min_size_gb", 0) or size_gb > site_cfg.get("max_size_gb", 9999):
                continue
            if item.get("seeders", 0) < site_cfg.get("min_seeders", 0):
                continue
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

    else:
        # Cookie-based NexusPHP sites — use pt_search.py subprocess
        keyword = site_cfg.get("search_keyword", "") or ""
        if not keyword:
            return [{"error": f"search_keyword not set for {site_id}", "source": site_id}]
        max_results = site_cfg.get("max_results", 50)
        search_script = os.path.join(_skill_dir, "pt_search.py")
        r = subprocess.run(
            ["python3", search_script, keyword, "--site", site_id, "--limit", str(max_results)],
            capture_output=True, text=True, timeout=60,
        )
        try:
            items = json.loads(r.stdout)
        except json.JSONDecodeError:
            return [{"error": f"{site_id} search parse error", "source": site_id}]

        for item in items:
            if "error" in item:
                continue
            promo = item.get("promo", "")
            if promo not in ("Free", "2xFree"):
                continue
            if site_cfg.get("exclude_hr", True) and "HR" in item.get("title", ""):
                continue
            size_bytes = item.get("size_bytes", 0)
            if size_bytes == 0:
                # size_bytes may be 0 for classic parser — try parsing size string
                size_str = item.get("size", "")
                size_bytes = _parse_size(size_str)
            size_gb = size_bytes / (1024**3)
            if size_gb < site_cfg.get("min_size_gb", 0) or size_gb > site_cfg.get("max_size_gb", 9999):
                continue
            if item.get("seeders", 0) < site_cfg.get("min_seeders", 0):
                continue
            if not item.get("download_url"):
                continue
            results.append(item)

    return results


def cleanup_aged(cfg: dict, qb: QBit, dry_run: bool = False) -> list[dict]:
    """Delete boost torrents seeding longer than max_seed_days."""
    g = cfg["global"]
    torrents = qb.list_torrents(g["boost_category"])
    now = time.time()
    max_age = g["max_seed_days"] * 86400
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
            "message": f"待删 {len(to_delete)} 个超过上限 {MAX_DELETE_PER_RUN}，中止。",
        }, ensure_ascii=False, indent=2))
        return []

    if dry_run:
        preview = {
            "check_mode": True,
            "category": g["boost_category"],
            "max_seed_days": g["max_seed_days"],
            "total_in_category": len(torrents),
            "would_delete": len(to_delete),
            "would_delete_list": [{
                "hash": t["hash"][:12],
                "name": t["name"][:80],
                "age_days": round((now - t.get("added_on", 0)) / 86400, 1),
                "size": _fmt_size(t.get("size", 0)),
            } for t in to_delete],
            "tip": "确认删除请运行: python3 scripts/pt_ratio_boost.py cleanup",
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return to_delete

    if to_delete:
        hashes = [t["hash"] for t in to_delete]
        backup_from_torrents(to_delete, reason="boost_aged")
        qb.delete_torrents(hashes, delete_files=g.get("delete_files", True))
        print(f"🧹 清理 {len(to_delete)} 个过期种子 (>{g['max_seed_days']}天)")

    return to_delete


def cleanup_dead(cfg: dict, qb: QBit, dry_run: bool = False) -> list[dict]:
    """Delete stalledDL torrents older than dead_seed_hours."""
    g = cfg["global"]
    torrents = qb.list_torrents(g["boost_category"])
    now = time.time()
    dead_hours = g.get("dead_seed_hours", 48)
    threshold = dead_hours * 3600
    to_delete = []

    for t in torrents:
        if t.get("state", "") != "stalledDL":
            continue
        added_on = t.get("added_on", 0)
        age = now - added_on
        if age > threshold:
            to_delete.append(t)

    if dry_run and to_delete:
        print(json.dumps({
            "check_mode": True,
            "dead_seed_hours": dead_hours,
            "stalled_dead": [{
                "hash": t["hash"][:12],
                "name": t["name"][:80],
                "age_hours": round((now - t.get("added_on", 0)) / 3600, 1),
            } for t in to_delete],
            "tip": "These stalled dead torrents would be deleted.",
        }, ensure_ascii=False, indent=2))
        return to_delete

    if to_delete:
        backup_from_torrents(to_delete, reason="boost_dead")
        qb.delete_torrents([t["hash"] for t in to_delete], delete_files=g.get("delete_files", True))
        print(f"💀 清理 {len(to_delete)} 个死种 (stalledDL >{dead_hours}h)")

    return to_delete


def add_new(cfg: dict, qb: QBit) -> list[dict]:
    """Search for and add new freeleech torrents."""
    g = cfg["global"]
    current = qb.list_torrents(g["boost_category"])
    slots = g["max_torrents"] - len(current)
    add_limit = cfg.get("per_run_add_limit", 5)
    if slots <= 0:
        print(f"📦 已达上限 {g['max_torrents']}，跳过新增")
        return []

    added = []
    for site_id, site_cfg in cfg.get("sites", {}).items():
        if len(added) >= min(slots, add_limit):
            break
        results = search_freeleech(site_id, site_cfg, g)
        for item in results:
            if len(added) >= min(slots, add_limit):
                break
            dl_url = item.get("download_url", "")
            if not dl_url:
                continue
            ok = qb.add_torrent(dl_url, g["boost_category"], g["boost_save_path"])
            if ok:
                added.append(item)
                print(f"➕ {item.get('title', '?')[:60]} ({item.get('size', '?')})")

    return added


def show_status(cfg: dict, qb: QBit):
    g = cfg["global"]
    torrents = qb.list_torrents(g["boost_category"])
    now = time.time()

    total_upload = sum(t.get("uploaded", 0) for t in torrents)
    total_download = sum(t.get("downloaded", 0) for t in torrents)
    ratio = total_upload / total_download if total_download > 0 else float("inf")

    print(f"\n📊 刷流状态 ({g['boost_category']})")
    print(f"   当前种子: {len(torrents)}/{g['max_torrents']}")
    print(f"   总上传: {_fmt_size(total_upload)}")
    print(f"   总下载: {_fmt_size(total_download)}")
    print(f"   分享率: {ratio:.2f}")
    print(f"   最大做种: {g['max_seed_days']} 天")
    print(f"   死种阈值: {g.get('dead_seed_hours', 48)} 小时")

    if torrents:
        torrents.sort(key=lambda t: t.get("added_on", 0))
        for t in torrents[:10]:
            age_days = (now - t.get("added_on", 0)) / 86400
            state = t.get("state", "")
            icon = "💀" if state == "stalledDL" else ("🧹" if age_days > g["max_seed_days"] else "🔄")
            print(f"   {icon} {age_days:4.0f}d | {t['name'][:50]}")


def main():
    cfg = load_config()

    if not cfg.get("enabled"):
        print("⚠️ 刷流未启用。编辑 pt_boost.json 设置 enabled: true")
        sys.exit(0)

    g = cfg["global"]
    qb_url = _env("QBITTORRENT_URL", "")
    qb_user = _env("QBITTORRENT_USER", "")
    qb_pass = _env("QBITTORRENT_PASS", "")

    if not all([qb_url, qb_user, qb_pass]):
        print("❌ qBittorrent 配置不完整，检查 secrets.env 中的 QBITTORRENT_URL/USER/PASS")
        sys.exit(1)

    if not g.get("boost_save_path"):
        print("❌ 未设置 boost_save_path")
        sys.exit(1)

    try:
        qb = QBit(qb_url, qb_user, qb_pass)
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
            print(json.dumps({"check_mode": True, "message": "run --check: preview only"}, ensure_ascii=False))
            cleanup_aged(cfg, qb, dry_run=True)
            cleanup_dead(cfg, qb, dry_run=True)
            show_status(cfg, qb)
        else:
            cleanup_aged(cfg, qb, dry_run=False)
            cleanup_dead(cfg, qb, dry_run=False)
            add_new(cfg, qb)
            show_status(cfg, qb)
    else:
        print("Usage: pt_ratio_boost.py [run|cleanup|status] [--check]")


if __name__ == "__main__":
    main()
