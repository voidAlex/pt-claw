#!/usr/bin/env python3
"""Cross-check PT actor-search results vs javbus filmography for pre-releases.

Usage:
    python3 scripts/chase_crosscheck.py /tmp/jbcheck/YYYYMMDD

Reads pt_<key>.json (pt_search.py output) and jb_<key>_p*.json (javbus-api pages)
in the given dir. Extracts codes from PT result titles via regex, diffs against
javbus filmography codes. Codes present on PT but absent from javbus = likely
M-Team pre-releases (PT 上架早于 javbus 收录) — these are new candidates that
the javbus-driven batch pipeline would miss, so this step is NOT skippable.

Output: per-key list of PT codes not in javbus filmography.

Verified 2026-08-20: 5 actors, all 0 pre-releases (REBDB-883 was a known
non-standard photo code, not new).
"""
import glob, json, os, re, sys

CODE_RE = re.compile(r'\b([A-Z]{2,6}[-_ ]?\d{2,5})\b', re.IGNORECASE)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    d = sys.argv[1]
    keys = sorted({os.path.splitext(os.path.basename(f).split('_', 1)[1])[0]
                   for f in glob.glob(os.path.join(d, 'pt_*.json'))})
    for key in keys:
        try:
            pt = json.load(open(os.path.join(d, f'pt_{key}.json')))
        except Exception:
            continue
        jb_codes = set()
        for f in glob.glob(os.path.join(d, f'jb_{key}_p*.json')):
            try:
                jb = json.load(open(f))
            except Exception:
                continue
            for m in jb.get('movies', []):
                cid = (m.get('id') or '').strip().upper()
                if cid:
                    jb_codes.add(cid)
        pt_codes = {}
        for r in pt.get('results', []):
            m = CODE_RE.search(r.get('title') or '')
            if m:
                code = m.group(1).upper().replace(' ', '').replace('_', '-')
                pt_codes.setdefault(code, []).append((r.get('site'), (r.get('title') or '')[:60]))
        extra = {c: v for c, v in pt_codes.items() if c not in jb_codes}
        print(f"== {key}: PT unique {len(pt_codes)}, 不在 javbus 片单: {len(extra)}")
        for c, v in sorted(extra.items()):
            print(f"   PRE-RELEASE? {c}: {v[0][0]} | {v[0][1]}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
