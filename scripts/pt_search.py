#!/usr/bin/env python3
"""
Lightweight multi-PT-site search — zero services, direct HTTP.

Usage:
    python3 pt_search.py "流浪地球2"              # search all configured sites
    python3 pt_search.py "流浪地球2" --site 1ptba  # single site
    python3 pt_search.py "流浪地球2" --limit 10    # per-site limit
    python3 pt_search.py "流浪地球2" --no-cache    # bypass result cache

Config:
    Environment variables:
      PT_COOKIE_<SITE>  — cookie strings (one per site, from browser)
      MTEAM_API_KEY     — M-Team API key
      PT_PROXY          — proxy for sites that need it (auto-applied per site)
    This script's SITES dict    — site search URLs & parser type

Output: JSON array of results across all sites.
"""

import json, os, re, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

from _common import _load_env_file, _env, _fmt_size, _env_matching, _is_login_page
from _http import fetch
from _logger import get_logger
from _search_cache import cache_get, cache_put

log = get_logger("pt_search")

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "secrets.env")

# NexusPHP promo CSS classes — aligned with PT-depiler NexusPHP.ts spstate enum
_PROMO_PATTERNS = [
    (r'class="[^"]*pro_free2up[^"]*"', "2xFree"),
    (r'class="[^"]*pro_50pctdown2up[^"]*"', "2x50%"),
    (r'class="[^"]*pro_2up[^"]*"', "2xUp"),
    (r'class="[^"]*pro_free[^"]*"', "Free"),
    (r'class="[^"]*pro_50pctdown[^"]*"', "50%"),
    (r'class="[^"]*pro_30pctdown[^"]*"', "30%"),
    (r'class="[^"]*pro_halfdown[^"]*"', "50%"),
    (r'class="[^"]*pro_30percent[^"]*"', "30%"),
    (r'class="[^"]*pro_custom[^"]*"', "Custom"),
    (r'class="[^"]*free[^"]*".*class="[^"]*twoup[^"]*"', "2xFree"),
    (r'class="[^"]*twoup[^"]*"', "2xUp"),
    (r'class="[^"]*(?:^|\s)(?:free|_free)(?:\s|")[^"]*"', "Free"),
    (r'>\s*Free\s*<', "Free"),
    (r'>\s*2\s*x\s*Free\s*<', "2xFree"),
    (r'>\s*50\s*%\s*<', "50%"),
    (r'>\s*30\s*%\s*<', "30%"),
]


def _detect_promo(html_block: str) -> str:
    for pattern, label in _PROMO_PATTERNS:
        if re.search(pattern, html_block, re.IGNORECASE):
            return label
    return ""


# ── Site Registry ───────────────────────────────────────────
SITES = {
    "1ptba": {
        "name": "1PTBar",
        "url": "https://1ptba.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["综合", "影视"],
    },
    "btschool": {
        "name": "BTSCHOOL",
        "url": "https://pt.btschool.club",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合", "学习"],
    },
    "carpt": {
        "name": "CarPT",
        "url": "https://carpt.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "hdfans": {
        "name": "HDFans",
        "url": "https://hdfans.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["综合", "影视"],
    },
    "mteam": {
        "name": "M-Team",
        "url": "https://kp.m-team.cc",
        "api_host": "https://api.m-team.cc/api",
        "api_token": _env("MTEAM_API_KEY", ""),
        "parser": "mteam_api",
        "needs_proxy": True,
        "categories": ["影视", "综合", "成人"],
    },
    "pttime": {
        "name": "PTTime",
        "url": "https://www.pttime.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["影视", "综合", "成人"],
    },
    "soulvoice": {
        "name": "SoulVoice",
        "url": "https://pt.soulvoice.club",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合", "电子书", "有声书"],
    },
    "zmpt": {
        "name": "织梦",
        "url": "https://zmpt.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "ptskit": {
        "name": "PTSkit",
        "url": "https://www.ptskit.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["短剧", "成人"],
        "adult_search": "/special.php?search={query}&notnewword=1",
    },
    "pthome": {
        "name": "PTHome",
        "url": "https://pthome.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "hdsky": {
        "name": "HDSky",
        "url": "https://hdsky.me",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "纪录片", "综合"],
    },
    "hdhome": {
        "name": "HDHome",
        "url": "https://hdhome.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "audiences": {
        "name": "Audiences",
        "url": "https://audiences.me",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "keepfrds": {
        "name": "KeepFriends",
        "url": "https://pt.keepfrds.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "ttg": {
        "name": "ToTheGlory",
        "url": "https://totheglory.im",
        "search": "/browse.php?search_field={query}&c=M",
        "parser": "ttg",
        "needs_proxy": True,
        "categories": ["影视", "音乐", "游戏", "综合"],
    },
    # ── Extended sites (from PT Depiler NexusPHP definitions) ────────
    "13city": {
        "name": "13城",
        "url": "https://13city.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "52movie": {
        "name": "52Movie",
        "url": "https://www.52movie.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合"],
    },
    "52pt": {
        "name": "52PT",
        "url": "https://52pt.site",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["高清", "电影", "电视剧"],
    },
    "afun": {
        "name": "Afun",
        "url": "https://www.ptlover.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "电影", "电视剧", "纪录片", "成人"],
    },
    "agsvpt": {
        "name": "AGSVPT",
        "url": "https://pt.agsvpt.cn",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "短剧", "影视"],
    },
    "alingpt": {
        "name": "alingPT",
        "url": "https://pt.aling.de",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "azusa": {
        "name": "梓喵",
        "url": "https://azusa.wiki",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["漫画", "轻小说", "Galgame", "画集"],
    },
    "baozi": {
        "name": "包子",
        "url": "https://p.t-baozi.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合"],
    },
    "byrbt": {
        "name": "北邮人",
        "url": "https://byr.pt",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["教育网", "影视", "综合"],
    },
    "cbg": {
        "name": "藏宝阁",
        "url": "https://cangbao.ge",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "cdy": {
        "name": "传道院",
        "url": "https://pt.cdy.skin",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合"],
    },
    "chdbits": {
        "name": "CHDBits",
        "url": "https://ptchdbits.co",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "crabpt": {
        "name": "蟹黄堡",
        "url": "https://crabpt.vip",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "cspt": {
        "name": "财神",
        "url": "https://cspt.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "cyanbug": {
        "name": "大青虫",
        "url": "https://cyanbug.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "discfan": {
        "name": "碟粉",
        "url": "https://discfan.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "dragonhd": {
        "name": "龍之家",
        "url": "https://www.dragonhd.xyz",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "dstudio": {
        "name": "DepthStudio",
        "url": "https://dstudio.me",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "dubhe": {
        "name": "天枢",
        "url": "https://dubhe.site",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "freefarm": {
        "name": "自由农场",
        "url": "https://pt.0ff.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["电视剧", "韩剧", "日剧"],
    },
    "ggpt": {
        "name": "GGPT",
        "url": "https://www.gamegamept.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["游戏"],
    },
    "haidan": {
        "name": "海胆",
        "url": "https://www.haidan.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["电影", "电视剧", "影视", "综合"],
    },
    "hdarea": {
        "name": "HDArea",
        "url": "https://hdarea.club",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "hdbao": {
        "name": "HDBao",
        "url": "https://hdbao.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "hdcity": {
        "name": "天使",
        "url": "https://hdcity.city",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "hdclone": {
        "name": "HDClone",
        "url": "https://pt.hdclone.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "hddolby": {
        "name": "HDDolby",
        "url": "https://www.hddolby.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "hdkylin": {
        "name": "HDKylin",
        "url": "https://www.hdkyl.in",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "电影", "电视剧", "纪录片"],
    },
    "hdtime": {
        "name": "HDTime",
        "url": "https://hdtime.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "hdupt": {
        "name": "HDU",
        "url": "https://pt.hdupt.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "hdvideo": {
        "name": "HDVideo",
        "url": "https://hdvideo.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "hhanclub": {
        "name": "憨憨",
        "url": "https://hhanclub.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["电影", "电视剧"],
    },
    "hitpt": {
        "name": "百川PT",
        "url": "https://www.hitpt.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["教育网", "影视", "综合"],
    },
    "htpt": {
        "name": "海棠",
        "url": "https://www.htpt.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["曲艺", "小品", "有声小说"],
    },
    "hudbt": {
        "name": "蝴蝶",
        "url": "https://hudbt.hust.edu.cn",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["教育网", "影视", "综合"],
    },
    "hxpt": {
        "name": "好学",
        "url": "https://www.hxpt.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["学习"],
    },
    "ilolicon": {
        "name": "爱萝莉",
        "url": "https://mua.xloli.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["萝莉", "动漫", "成人", "综合", "影视"],
    },
    "itzmx": {
        "name": "PT分享站",
        "url": "https://pt.itzmx.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合"],
    },
    "joyhd": {
        "name": "JoyHD",
        "url": "https://www.joyhd.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "kamept": {
        "name": "龟站",
        "url": "https://kamept.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["成人", "COS", "动漫", "音乐", "影视"],
    },
    "kelu": {
        "name": "Kelu",
        "url": "https://our.kelu.one",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["成人"],
    },
    "kufei": {
        "name": "库非",
        "url": "https://kufei.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "kunlun": {
        "name": "昆仑",
        "url": "https://www.yhpp.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "lajidui": {
        "name": "垃圾堆",
        "url": "https://pt.lajidui.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视综艺", "游戏软件", "电子书"],
    },
    "lemonhdnet": {
        "name": "柠檬不甜",
        "url": "https://lemonhd.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合"],
    },
    "longpt": {
        "name": "龙PT",
        "url": "https://longpt.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视", "动漫", "有声书"],
    },
    "luckpt": {
        "name": "LuckPT",
        "url": "https://pt.luckpt.de",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合", "音乐"],
    },
    "march": {
        "name": "三月传媒",
        "url": "https://duckboobee.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["WEB", "综合"],
    },
    "momentpt": {
        "name": "瞬间",
        "url": "https://www.momentpt.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["摄影", "图片", "艺术"],
    },
    "musopia": {
        "name": "音乐乌托邦",
        "url": "https://www.musopia.vip",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["音乐"],
    },
    "muxuege": {
        "name": "慕雪阁",
        "url": "https://pt.muxuege.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合"],
    },
    "mypt": {
        "name": "MyPT",
        "url": "https://cc.mypt.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合"],
    },
    "nanyangpt": {
        "name": "南洋PT",
        "url": "https://nanyangpt.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["教育网", "影视", "综合"],
    },
    "nexushd": {
        "name": "NexusHD",
        "url": "https://v6.nexushd.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["教育网"],
    },
    "nicept": {
        "name": "NicePT",
        "url": "https://www.nicept.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["成人"],
    },
    "njtupt": {
        "name": "浦园",
        "url": "https://njtupt.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "novahd": {
        "name": "NovaHD",
        "url": "https://pt.novahd.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合"],
    },
    "okpt": {
        "name": "OKPT",
        "url": "https://www.okpt.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "opencd": {
        "name": "皇后",
        "url": "https://open.cd",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["音乐"],
    },
    "oshenpt": {
        "name": "奥申",
        "url": "https://www.oshen.win",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "音乐"],
    },
    "ourbits": {
        "name": "OurBits",
        "url": "https://ourbits.club",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "动漫", "纪录片", "综艺"],
    },
    "pandapt": {
        "name": "熊猫",
        "url": "https://pandapt.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "piggo": {
        "name": "Piggo",
        "url": "https://piggo.me",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合", "少儿"],
    },
    "playletpt": {
        "name": "PlayLet",
        "url": "https://playletpt.xyz",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["短剧"],
    },
    "ptcafe": {
        "name": "咖啡",
        "url": "https://ptcafe.club",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "pter": {
        "name": "PTer",
        "url": "https://pterclub.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "ptfans": {
        "name": "PTFans",
        "url": "https://ptfans.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合", "成人"],
    },
    "ptgtk": {
        "name": "PTGTK",
        "url": "https://pt.gtkpw.xyz",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "ptlao": {
        "name": "PTLAO",
        "url": "https://ptlao.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["成人", "综合"],
    },
    "ptlgs": {
        "name": "PTLGS",
        "url": "https://ptlgs.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "ptneko": {
        "name": "超科学喵",
        "url": "https://ptneko.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": [],
    },
    "ptsbao": {
        "name": "烧包",
        "url": "https://ptsbao.club",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "ptzone": {
        "name": "PTZone",
        "url": "https://ptzone.xyz",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "railgunpt": {
        "name": "RailgunPT",
        "url": "https://bilibili.download",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合"],
    },
    "raingfh": {
        "name": "雨",
        "url": "https://raingfh.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "retroflix": {
        "name": "RetroFlix",
        "url": "https://retroflix.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "rousi": {
        "name": "肉丝",
        "url": "https://rousi.zip",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合", "成人"],
    },
    "rs": {
        "name": "睿思",
        "url": "https://resource.xidian.edu.cn",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["教育网", "影视", "综合"],
    },
    "sbpt": {
        "name": "SBPT",
        "url": "https://sbpt.link",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "sewerpt": {
        "name": "下水道",
        "url": "https://sewerpt.com",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["冷门", "低分", "粤语", "影视"],
    },
    "siqi": {
        "name": "思齐",
        "url": "https://si-qi.xyz",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["图书"],
    },
    "sjtu": {
        "name": "葡萄",
        "url": "https://pt.sjtu.edu.cn",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["教育网", "影视", "综合"],
    },
    "springsunday": {
        "name": "春天",
        "url": "https://springsunday.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "音乐", "综合"],
    },
    "sunnypt": {
        "name": "阳光",
        "url": "https://sunnypt.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "tangpt": {
        "name": "躺平",
        "url": "https://www.tangpt.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合"],
    },
    "tccf": {
        "name": "TCCF",
        "url": "https://et8.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合", "学习"],
    },
    "tey": {
        "name": "太乙",
        "url": "https://pt.tey.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["电视剧", "韩剧"],
    },
    "tjupt": {
        "name": "北洋",
        "url": "https://tjupt.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": False,
        "categories": ["教育网", "影视", "综合"],
    },
    "tlfbits": {
        "name": "TLF",
        "url": "https://pt.eastgame.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "综合"],
    },
    "tmpt": {
        "name": "唐门",
        "url": "https://tmpt.top",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "torrenthub": {
        "name": "TorrentHub",
        "url": "https://torrenthub.club",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "教育", "音乐"],
    },
    "tu88": {
        "name": "TU88",
        "url": "https://pt.tu88.men",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["漫画", "图集", "绘本", "成人"],
    },
    "u2": {
        "name": "U2",
        "url": "https://u2.dmhy.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视", "动漫"],
    },
    "ubits": {
        "name": "UBits",
        "url": "https://ubits.club",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["影视"],
    },
    "ultrahd": {
        "name": "UltraHD",
        "url": "https://ultrahd.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["电影", "电视剧", "综艺", "纪录片", "动漫"],
    },
    "wintersakura": {
        "name": "冬樱",
        "url": "https://wintersakura.net",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["电影", "电视剧"],
    },
    "xingtan": {
        "name": "杏坛",
        "url": "https://xingtan.one",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["医学", "电子书", "学术"],
    },
    "xingyunge": {
        "name": "星陨阁",
        "url": "https://pt.xingyungept.org",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视", "国漫"],
    },
    "yinguskg": {
        "name": "樱花",
        "url": "https://pt.ying.us.kg",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["综合", "影视"],
    },
    "zrpt": {
        "name": "ZRPT",
        "url": "https://zrpt.cc",
        "search": "/torrents.php?search={query}&notnewword=1",
        "parser": "nexusphp",
        "needs_proxy": True,
        "categories": ["纪录片", "自然", "教育"],
    },
}


def load_cookies() -> dict[str, str]:
    """Load cookie strings from environment variables (PT_COOKIE_<SITE>).
    Falls back to secrets.env if not in process environment."""
    cookies = {}
    for key, val in _env_matching("PT_COOKIE_").items():
        site_id = key[len("PT_COOKIE_"):].lower()
        cookies[site_id] = val
    return cookies


def search_site(site_id: str, site: dict, query: str, limit: int,
                timeout: int = 15, adult: bool = False) -> list[dict]:
    """Search a single PT site. Returns list of result dicts."""
    # API-based sites (no cookie/HTTP needed)
    if site.get("parser") == "mteam_api":
        return _search_mteam_api(site, query, limit, adult=adult)

    cookies = load_cookies()
    cookie_str = cookies.get(site_id, "")

    if not cookie_str:
        log.warning("no cookie for site=%s site_id=%s", site["name"], site_id)
        return [{"error": f"No cookie configured for {site['name']}",
                 "site": site["name"], "site_id": site_id}]

    if adult and site_id == "pttime":
        search_path = f"/adults.php?search={urllib.parse.quote(query)}&search_area=1&incldead=1&spstate=0"
    elif adult and "adult_search" in site:
        search_path = site["adult_search"].format(query=urllib.parse.quote(query))
    else:
        search_path = site["search"].format(query=urllib.parse.quote(query))
    full_url = f"{site['url']}{search_path}"

    proxy = _env("PT_PROXY") if site.get("needs_proxy") else None
    log.info("searching site=%s query=%s proxy=%s", site_id, query, bool(proxy))
    try:
        status, html, elapsed = fetch(
            full_url,
            headers={"Cookie": cookie_str},
            proxy=proxy,
            warmup=(proxy is not None),
        )
    except Exception as e:
        log.error("fetch failed site=%s url=%s error=%s", site_id, full_url, e)
        return [{"error": str(e), "site": site["name"], "site_id": site_id}]

    log.info("fetched site=%s status=%d elapsed=%.1fs", site_id, status, elapsed)

    if _is_login_page(html):
        log.warning("login page detected site=%s — cookie expired", site_id)
        return [{"error": "Cookie expired — re-login needed",
                 "site": site["name"], "site_id": site_id}]

    # Parse
    if site["parser"] == "nexusphp":
        results = _parse_nexusphp(html, site, site_id, limit)
        if not results or ("error" in (results[0] if results else {})):
            results = _parse_nexusphp_classic(html, site, site_id, limit)
        return results
    elif site["parser"] == "mteam_api":
        return _search_mteam_api(site, query, limit, adult=adult)
    elif site["parser"] == "ttg":
        return _parse_ttg(html, site, site_id, limit)
    else:
        log.warning("unknown parser type=%s site=%s", site.get("parser"), site_id)
        return [{"error": f"Unsupported parser type: {site.get('parser')}",
                 "site": site["name"], "site_id": site_id}]


def _parse_nexusphp_classic(html: str, site: dict, site_id: str,
                           limit: int) -> list[dict]:
    """Parse classic NexusPHP — same structure as PTTime but no data= attr.

    Each torrent: title <tr> + stats cells between that </tr> and next <tr.
    """
    results = []
    seen_ids = set()

    # Find all download links
    dl_matches = list(re.finditer(
        r'href="(download\.php\?id=(\d+)[^"]*)"', html))

    for dl_match in dl_matches:
        dl_url = dl_match.group(1)
        tid = dl_match.group(2)
        if tid in seen_ids:
            continue
        seen_ids.add(tid)

        # Find enclosing <tr> — the title row
        before = html[:dl_match.start()]
        tr_start = before.rfind('<tr')
        if tr_start == -1:
            continue

        # Find the title row's closing </tr> (handle nested <tr>)
        after_tr = html[tr_start:]
        depth = 0
        tr_close = 0
        for m in re.finditer(r'<(/?tr)\b', after_tr):
            if m.group(1) == 'tr':
                depth += 1
            else:
                if depth == 1:
                    tr_close = tr_start + m.end()
                    break
                depth -= 1

        title_html = html[tr_start:tr_close]

        # Stats: cells between title row's </tr> and next <tr> or </tbody>
        after_title = html[tr_close:]
        next_tr = re.search(r'<(?:tr\b|/tbody)', after_title)
        stats_end = tr_close + next_tr.start() if next_tr else tr_close + len(after_title)
        stats_html = html[tr_close:stats_end]

        # Title
        title = ""
        tm = re.search(r'<a[^>]*title="([^"]+)"[^>]*>', title_html)
        if tm:
            title = tm.group(1).strip()
        if not title or len(title) < 4:
            tm = re.search(
                r'href="details\.php\?id=' + tid + r'[^"]*"[^>]*>(.*?)</a>',
                title_html, re.DOTALL)
            if tm:
                title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
        if not title:
            continue

        # Size from stats cells
        size_str = ""
        sm = re.search(
            r'>\s*([\d.,]+)\s*(?:<br\s*/?>\s*)?(GB|MB|TB|KB)\s*<',
            stats_html, re.IGNORECASE)
        if sm:
            size_str = f"{sm.group(1)} {sm.group(2).upper()}"

        # Seeds: <b>N</b> in stats cells, first matches are seeders/leechers
        seeds = 0
        leech = 0
        seed_m = re.search(r'seeders[^>]*>\s*<b>(\d+)</b>', stats_html)
        if seed_m:
            seeds = int(seed_m.group(1))
        leech_m = re.search(r'leechers[^>]*>\s*<b>(\d+)</b>', stats_html)
        if leech_m:
            leech = int(leech_m.group(1))
        if seeds == 0:
            bolds = re.findall(r'<b>(\d+)</b>', stats_html)
            seeds = int(bolds[0]) if bolds else 0
            leech = int(bolds[1]) if len(bolds) > 1 else 0

        promo = _detect_promo(title_html + stats_html)

        results.append({
            "title": title.strip(),
            "size": size_str, "size_bytes": 0,
            "seeders": seeds, "leechers": leech,
            "category": "", "promo": promo,
            "download_url": site["url"] + "/" + dl_url,
            "site": site["name"], "site_id": site_id,
            "source": site_id,
        })
        if len(results) >= limit:
            break

    if not results:
        log.warning("no results parsed (classic) site=%s site_id=%s", site["name"], site_id)
        return [{"error": "No results found", "site": site["name"], "site_id": site_id}]
    results.sort(key=lambda r: r["seeders"], reverse=True)
    return results[:limit]


def _search_mteam_api(site: dict, query: str, limit: int, adult: bool = False) -> list[dict]:
    """Search M-Team via REST API. Delegates to mteam_api module."""
    log.info("mteam_api search query=%s limit=%d adult=%s", query, limit, adult)
    api_token = _env("MTEAM_API_KEY", "") or site.get("api_token", "")
    if not api_token:
        return [{"error": "No API token configured",
                 "site": site["name"], "site_id": "mteam"}]

    proxy = _env("PT_PROXY")
    if not proxy:
        return [{"error": "PT_PROXY not set — M-Team API requires proxy",
                 "site": site["name"], "site_id": "mteam"}]

    from mteam_api import search as mteam_search, get_download_url as mteam_dl_url

    items = mteam_search(query, api_token, limit=limit, adult=adult)

    if not items:
        return [{"error": "No results found", "site": site["name"],
                 "site_id": "mteam"}]
    if len(items) == 1 and "error" in items[0]:
        items[0]["site"] = site["name"]
        items[0]["site_id"] = "mteam"
        return items

    results = []
    for item in items:
        if "error" in item:
            continue
        dl_url = ""
        torrent_id = item.get("id", "")
        if torrent_id:
            dl_url = mteam_dl_url(torrent_id, api_token)
        results.append({
            "title": item.get("title", "").strip(),
            "detail_url": item.get("detail_url", ""),
            "download_url": dl_url,
            "size": item.get("size", ""),
            "size_bytes": item.get("size_bytes", 0),
            "seeders": item.get("seeders", 0),
            "leechers": item.get("leechers", 0),
            "category": item.get("category", ""),
            "promo": item.get("promo", ""),
            "site": site["name"],
            "site_id": "mteam",
            "source": "mteam",
        })

    if not results:
        return [{"error": "No results found", "site": site["name"],
                 "site_id": "mteam"}]

    results.sort(key=lambda r: r["seeders"], reverse=True)
    log.info("mteam_api results count=%d query=%s", len(results[:limit]), query)
    return results[:limit]


def _parse_nexusphp(html: str, site: dict, site_id: str,
                    limit: int) -> list[dict]:
    """Parse NexusPHP/PTTime torrent listing.

    Structure: each torrent spans from one <tr data=ID> to the next.
    Title in <tr data=ID>, stats (size, seeds) in cells between the
    title row closing and the next <tr data=ID>.
    """
    results = []

    # Find all <tr data=TID> or <tr data="TID"> start positions
    title_starts = [(m.start(), m.group(1), m.group(2))
                    for m in re.finditer(
                        r'<tr\s+data=["\']?(\d+)\b["\']?[^>]*>(.*?)</tr>',
                        html, re.DOTALL)]

    for idx, (start, torrent_id, title_html) in enumerate(title_starts):
        # The stats block is from the title row's closing </tr>
        # to the next <tr data=...> start (or end of HTML)
        title_row_end = start + len(re.search(
            r'<tr\s+data=["\']?' + torrent_id + r'\b["\']?[^>]*>.*?</tr>',
            html[start:], re.DOTALL).group(0))
        
        if idx + 1 < len(title_starts):
            stats_end = title_starts[idx + 1][0]
        else:
            # Last torrent — find next major section boundary
            stats_end = min(len(html), title_row_end + 5000)

        stats_html = html[title_row_end:stats_end]

        # Parse title
        title = ""
        tm = re.search(r'<a[^>]*title="([^"]+)"[^>]*>(.*?)</a>',
                       title_html, re.DOTALL)
        if tm:
            title = tm.group(1).strip()
            if len(title) < 5:
                title = re.sub(r'<[^>]+>', '', tm.group(2)).strip()
        if not title:
            tm = re.search(r'<a[^>]*>(.*?)</a>', title_html, re.DOTALL)
            if tm:
                title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
        if not title:
            continue

        # Parse stats
        size_str = ""
        size_bytes = 0
        sm = re.search(
            r'>\s*([\d.,]+)\s*(?:<br\s*/?>\s*)?(GB|MB|TB|KB|B)\s*<',
            stats_html, re.IGNORECASE)
        if sm:
            size_str = f"{sm.group(1)} {sm.group(2).upper()}"
            try:
                sz = float(sm.group(1).replace(",", ""))
                unit = sm.group(2).upper()
                mult = {"B": 1, "KB": 1024, "MB": 1048576,
                        "GB": 1073741824, "TB": 1099511627776}
                size_bytes = int(sz * mult.get(unit, 1))
            except ValueError:
                pass

        # Seeds: <b>N</b> in stats area. First <b> is almost always seeders.
        bolds = re.findall(r'<b>(\d+)</b>', stats_html)
        seeders = int(bolds[0]) if bolds else 0
        leechers = int(bolds[1]) if len(bolds) > 1 else 0

        promo = _detect_promo(title_html + stats_html)

        cat = re.search(r'<span[^>]*title="([^"]*)"', title_html)
        category = cat.group(1) if cat else ""

        dl = re.search(r'download\.php\?id=' + torrent_id + r'[^"\'\s]*', html)
        dl_url = (site["url"] + "/" + dl.group(0)) if dl else ""

        results.append({
            "title": title.strip(),
            "size": size_str,
            "size_bytes": size_bytes,
            "seeders": seeders,
            "leechers": leechers,
            "category": category,
            "promo": promo,
            "download_url": dl_url,
            "site": site["name"],
            "site_id": site_id,
            "source": site_id,
        })

        if len(results) >= limit:
            break

    if not results:
        log.warning("no results parsed site=%s site_id=%s", site["name"], site_id)
        return [{"error": "No results found", "site": site["name"],
                 "site_id": site_id}]

    results.sort(key=lambda r: r["seeders"], reverse=True)
    return results[:limit]


def _parse_ttg(html, site, site_id, limit):
    """Parse TTG (TBSource schema) torrent listing.

    Rows are <tr id="TID"> inside table#torrent_table.
    Title in <div class="name_left"> -> <a><b><font>TITLE</font></b></a> or <a><b>TITLE</b></a>.
    Download: <a class="dl_a" href="...">.
    Size: 7th <td>, Completed: 8th <td>, Seeders/Leechers: 9th <td> as "N/N".
    Promo: img[alt='free'] -> Free, img[alt='30%'] -> 30%, img[alt='50%'] -> 50%,
           span.browse.excl -> Excl.
    """
    results = []
    seen_ids = set()

    # Find torrent table rows with id attribute
    row_matches = list(re.finditer(
        r'<tr\b[^>]*\bid=["\']?(\d+)["\']?[^>]*>(.*?)</tr>',
        html, re.DOTALL | re.IGNORECASE))

    for row_match in row_matches:
        tid = row_match.group(1)
        if tid in seen_ids:
            continue
        seen_ids.add(tid)
        row_html = row_match.group(2)

        # Title: look inside <div class="name_left"> or similar
        title = ""
        sub_title = ""
        name_div_match = re.search(
            r'<div[^>]*class=["\']?name_left["\']?[^>]*>(.*?)</div>',
            row_html, re.DOTALL | re.IGNORECASE)
        if name_div_match:
            name_div_html = name_div_match.group(1)
            # Try <a><b><font>TITLE</font></b></a> first
            tm = re.search(
                r'<a[^>]*><b>(?:<font[^>]*>)?([^<]+)',
                name_div_html, re.DOTALL | re.IGNORECASE)
            if tm:
                title = tm.group(1).strip()
            if not title:
                # Try <a><b>TITLE</b></a>
                tm = re.search(
                    r'<a[^>]*><b>([^<]+)</b>',
                    name_div_html, re.DOTALL | re.IGNORECASE)
                if tm:
                    title = tm.group(1).strip()
            # subTitle: text after <br> inside the <b> element
            b_match = re.search(r'<b[^>]*>(.*?)</b>', name_div_html,
                                re.DOTALL | re.IGNORECASE)
            if b_match:
                b_inner = b_match.group(1)
                br_parts = re.split(r'<br\s*/?>', b_inner, maxsplit=1)
                if len(br_parts) > 1:
                    after_br = re.sub(r'<[^>]+>', '', br_parts[1]).strip()
                    if after_br:
                        sub_title = after_br
        if not title:
            # Broader fallback: first <b>TITLE</b> inside the row
            tm = re.search(r'<b>([^<]{4,})</b>', row_html)
            if tm:
                title = tm.group(1).strip()
        if not title:
            continue

        # Download link: <a class="dl_a" href="...">
        dl_url = ""
        dl_match = re.search(r'<a[^>]*class=["\']?dl_a["\']?[^>]*href=["\']([^"\']+)',
                             row_html, re.IGNORECASE)
        if dl_match:
            dl_url = site["url"] + "/" + dl_match.group(1)

        # Extract all <td> cells
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE)

        # Build column index mapping from <th> headers (fallback to hardcoded indices)
        col_size, col_completed, col_sl = 6, 7, 8
        header_block = re.search(
            r'<tr[^>]*>\s*(?:<th[^>]*>.*?</th>\s*)+</tr>',
            html, re.DOTALL | re.IGNORECASE)
        if header_block:
            ths = re.findall(r'<th[^>]*>(.*?)</th>', header_block.group(0), re.DOTALL | re.IGNORECASE)
            for i, th in enumerate(ths):
                th_text = re.sub(r'<[^>]+>', '', th).strip()
                if re.match(r'(大小|Size)', th_text, re.IGNORECASE):
                    col_size = i
                elif re.match(r'(完成|Completed)', th_text, re.IGNORECASE):
                    col_completed = i
                elif re.match(r'(做种.*下载|Seed.*Leech|S-L|S\/L)', th_text, re.IGNORECASE):
                    col_sl = i

        # Size
        size_str = ""
        if len(tds) > col_size:
            size_inner = re.sub(r'<[^>]+>', '', tds[col_size]).strip()
            sm = re.search(r'([\d.,]+)\s*(GB|MB|TB|KB)', size_inner, re.IGNORECASE)
            if sm:
                size_str = f"{sm.group(1)} {sm.group(2).upper()}"

        # Completed
        completed = 0
        if len(tds) > col_completed:
            completed_str = re.sub(r'<[^>]+>', '', tds[col_completed]).strip()
            try:
                completed = int(re.sub(r'[^\d]', '', completed_str))
            except ValueError:
                pass

        # Seeders/Leechers in format "N/N"
        seeders = 0
        leechers = 0
        if len(tds) > col_sl:
            sl_inner = re.sub(r'<[^>]+>', '', tds[col_sl]).strip()
            sl_match = re.search(r'(\d+)\s*/\s*(\d+)', sl_inner)
            if sl_match:
                seeders = int(sl_match.group(1))
                leechers = int(sl_match.group(2))

        # Promo detection
        promo = ""
        if re.search(r'<img[^>]+alt=["\']free["\']', row_html, re.IGNORECASE):
            promo = "Free"
        elif re.search(r'<img[^>]+alt=["\']50%["\']', row_html, re.IGNORECASE):
            promo = "50%"
        elif re.search(r'<img[^>]+alt=["\']30%["\']', row_html, re.IGNORECASE):
            promo = "30%"
        if re.search(r'<span[^>]*class=["\'][^"\']*browse\.excl[^"\']*["\']',
                      row_html, re.IGNORECASE):
            promo = (promo + " Excl").strip() if promo else "Excl"

        result = {
            "title": title.strip(),
            "size": size_str,
            "size_bytes": 0,
            "seeders": seeders,
            "leechers": leechers,
            "category": "",
            "promo": promo,
            "download_url": dl_url,
            "site": site["name"],
            "site_id": site_id,
            "source": site_id,
        }
        if sub_title:
            result["sub_title"] = sub_title
        results.append(result)
        if len(results) >= limit:
            break

    if not results:
        return [{"error": "No results found", "site": site["name"], "site_id": site_id}]

    results.sort(key=lambda r: r["seeders"], reverse=True)
    return results[:limit]


def main():
    raw_args = sys.argv[1:]

    if "--help" in raw_args or "-h" in raw_args:
        print(__doc__)
        sys.exit(0)

    # Parse named flags
    flags = {}
    positional = []
    skip_next = False
    for i, a in enumerate(raw_args):
        if skip_next:
            skip_next = False
            continue
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(raw_args) and not raw_args[i + 1].startswith("--"):
                flags[key] = raw_args[i + 1]
                skip_next = True
            else:
                flags[key] = True
        else:
            positional.append(a)

    query = " ".join(positional)
    if not query:
        print(json.dumps({"error": "No search query provided"}))
        sys.exit(1)

    # Which sites to search
    target_sites = {}
    if "site" in flags:
        site_id = flags["site"]
        if site_id in SITES:
            target_sites[site_id] = SITES[site_id]
        else:
            print(json.dumps({"error": f"Unknown site: {site_id}"}))
            sys.exit(1)
    else:
        target_sites = {k: v for k, v in SITES.items()}

    # Limit
    try:
        limit = int(flags.get("limit", 20))
    except (ValueError, TypeError):
        print(json.dumps({"error": f"Invalid --limit value: {flags.get('limit')}"}))
        sys.exit(1)
    adult = flags.get("adult", False)
    actor = flags.get("actor", "")
    no_cache = "no-cache" in flags

    log.info("invoked query=%s sites=%d limit=%d adult=%s actor=%s",
             query, len(target_sites), limit, adult, actor)

    if adult and actor and "pttime" in target_sites:
        s = target_sites["pttime"]
        search_path = f"/adults.php?search={urllib.parse.quote(actor)}&search_area=1&incldead=1"
        full_url = f"{s['url']}{search_path}"
        cookies = load_cookies()
        cookie_str = cookies.get("pttime", "")
        if not cookie_str:
            print(json.dumps({"error": "No cookie configured for PTTime"}))
            sys.exit(1)
        proxy = _env("PT_PROXY") if s.get("needs_proxy") else None
        try:
            status, html, elapsed = fetch(
                full_url,
                headers={"Cookie": cookie_str},
                proxy=proxy,
                warmup=(proxy is not None),
            )
        except Exception as e:
            log.error("PTTime actor search failed error=%s", e)
            print(json.dumps({"error": str(e), "site": "PTTime"}))
            sys.exit(1)
        results = _parse_nexusphp(html, s, "pttime", limit)
        if not results or ("error" in (results[0] if results else {})):
            results = _parse_nexusphp_classic(html, s, "pttime", limit)
        print(json.dumps({"query": f"actor:{actor}", "total": len(results),
                          "results": results}, ensure_ascii=False, indent=2))
        return

    # Search all sites
    all_results = []
    errors = []

    if len(target_sites) == 1:
        # Single site — no thread pool overhead
        sid, site = next(iter(target_sites.items()))
        if not no_cache:
            cached = cache_get(sid, query)
            if cached is not None:
                all_results.extend(cached)
            else:
                results = search_site(sid, site, query, limit, adult=adult)
                valid = [item for item in results if "error" not in item]
                if valid:
                    cache_put(sid, query, valid)
                for item in results:
                    if "error" in item:
                        errors.append(item)
                    else:
                        all_results.append(item)
        else:
            for item in search_site(sid, site, query, limit, adult=adult):
                if "error" in item:
                    errors.append(item)
                else:
                    all_results.append(item)
    else:
        # Multi-site parallel
        with ThreadPoolExecutor(max_workers=min(len(target_sites), 5)) as executor:
            futures = {}
            for sid, site in target_sites.items():
                if not no_cache:
                    cached = cache_get(sid, query)
                    if cached is not None:
                        all_results.extend(cached)
                        continue
                future = executor.submit(search_site, sid, site, query, limit, adult=adult)
                futures[future] = sid
            for future in as_completed(futures):
                sid = futures[future]
                try:
                    r = future.result()
                    valid = [item for item in r if "error" not in item]
                    if valid and not no_cache:
                        cache_put(sid, query, valid)
                    for item in r:
                        if "error" in item:
                            errors.append(item)
                        else:
                            all_results.append(item)
                except Exception as e:
                    log.error("site %s failed error=%s", sid, e)
                    errors.append({"error": str(e), "site": SITES[sid]["name"],
                                   "site_id": sid})

    # Sort all results by seeders descending
    all_results.sort(key=lambda r: r.get("seeders", 0), reverse=True)

    output = {
        "query": query,
        "total": len(all_results),
        "errors": errors,
        "results": all_results,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
