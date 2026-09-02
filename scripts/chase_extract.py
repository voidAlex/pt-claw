#!/usr/bin/env python3
"""
追剧候选提取 + 过滤（cron 安全，无管道；追剧流水线第 ② 步）。

用法:
  cd /home/alex/.hermes/skills/media/pt-claw
  python3 scripts/chase_extract.py /tmp/jbcheck/20260824

读取指定目录下所有 jb_<key>_p*.json（javbus-api 片单，顺序直连 curl 落盘），
提取每条 movie 的 m['id'] 番号，按已验证规则过滤，输出:
  - codes.txt           候选番号（每行一个，供 download_history filter 与 jf_batch_check 用）
  - candidates_full.tsv 候选明细（actor/code/date/title，供人工核对）

过滤规则（勿擅改，见 references/cron-chase-lessons.md「非标准内容过滤」节）:
  1. NONSTD 前缀（锚定 '-'）: REBD/REBDB/SIVR/MBDD/OFJE/IPOK/PFES/FWAY/IPVR/MBRBA/THN/THU/PPR/PPX/SS
  2. OAE 仅当标题含 "ALL NUDE" 才过滤（OAE-287 是正常剧情片，必须保留）
  3. wishlist exclude_prefixes（如 FNS/VR/3D）
  4. exclude_multi 演员排除 BEAUTY VENUS / HARLEM / 究極共演 标题标记

⚠️ 勿把 GNI/DLV 加进 NONSTD —— 它们是瀧本雫葉 正常作品（2026-08-23 事故，加了会丢资源）。
⚠️ 前缀判定必须 code == P 或 code.startswith(P + '-')，禁止裸 startswith(P)
   （裸 startswith('SS') 会误伤整个 SSIS 系列；裸 startswith('VR') 同理。2026-08-21 事故）。
⚠️ exclude_multi 的 BEAUTY VENUS 判定用系列级标记，禁止裸 '美人'
   （IPZZ-749「清楚美人お姉さん」是正常单人作，会被裸 '美人' 误删。2026-08-21 事故）。

演员 key→(名称, exclude_prefixes, exclude_multi) 映射需与 pt_wishlist.json 保持同步；
key 为 javbus 片单落盘文件名 jb_<key>_p<N>.json 的前缀（本仓库约定）。
"""
import json
import glob
import sys
from collections import Counter

ACTORS = {
    'asano':     ('浅野こころ', ['FNS'], False),
    'shinonome': ('東雲みれい', [], True),
    'takimoto':  ('瀧本雫葉', [], False),
    'fuua':      ('楓ふうあ', [], False),
    'aisai':     ('愛才りあ', ['VR', '3D'], True),
}

NONSTD = ['REBD', 'REBDB', 'SIVR', 'MBDD', 'OFJE', 'IPOK', 'PFES',
          'FWAY', 'IPVR', 'MBRBA', 'THN', 'THU', 'PPR', 'PPX', 'SS']
MULTI_MARKERS = ['BEAUTY VENUS', 'HARLEM', '究極共演']


def is_nonstd(code, title):
    for p in NONSTD:
        if code == p or code.startswith(p + '-'):
            return True
    if code == 'OAE' or code.startswith('OAE-'):
        if 'ALL NUDE' in (title or '').upper():
            return True
    return False


def is_excluded(code, prefixes):
    for p in prefixes:
        if code == p or code.startswith(p):
            return True
    return False


def is_multi(title):
    t = title or ''
    return any(m in t for m in MULTI_MARKERS)


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else '.'
    records = []
    for key, (name, excl_prefixes, excl_multi) in ACTORS.items():
        seen = set()
        for f in sorted(glob.glob(f'{d}/jb_{key}_p*.json')):
            data = json.load(open(f))
            for m in data.get('movies', []):
                code = m.get('id', '')
                title = m.get('title', '')
                date = m.get('date', '')
                if not code or code in seen:
                    continue
                seen.add(code)
                reason = None
                if is_nonstd(code, title):
                    reason = 'nonstd'
                elif is_excluded(code, excl_prefixes):
                    reason = 'exclude_prefix'
                elif excl_multi and is_multi(title):
                    reason = 'exclude_multi'
                records.append((key, name, code, date, title, reason))

    filtered = Counter(r[5] for r in records if r[5])
    cands = [r for r in records if r[5] is None]
    print(f'TOTAL={len(records)} CANDIDATES={len(cands)} FILTERED={dict(filtered)}')
    print('PER-ACTOR=', dict(Counter(r[0] for r in cands)))

    with open(f'{d}/codes.txt', 'w') as fh:
        for key, name, code, date, title, reason in cands:
            fh.write(code + '\n')
    with open(f'{d}/candidates_full.tsv', 'w') as fh:
        fh.write('actor\tcode\tdate\ttitle\n')
        for key, name, code, date, title, reason in cands:
            fh.write(f'{key}\t{code}\t{date}\t{title}\n')


if __name__ == '__main__':
    main()
