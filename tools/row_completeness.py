# -*- coding: utf-8 -*-
"""Row-level completeness report: which 序号 values are present / missing.

The 分项报价表 is a numbered table (序号 1..N). Extraction completeness is a
question of "which 序号 did we get", independent of the messy names, so this
groups extract_prices() output by the count field and lists the gaps.

Usage: py -3.12 tools/row_completeness.py <cache_prefix> [expected_max]
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402

CACHE = r'C:\Users\aiden\AppData\Local\星易查\extract_cache'


def main():
    prefix = sys.argv[1]
    expected = int(sys.argv[2]) if len(sys.argv) > 2 else None
    name = next(n for n in os.listdir(CACHE) if n.startswith(prefix))
    with open(os.path.join(CACHE, name), encoding='utf-8') as f:
        text = json.load(f)['t']
    subs = app.extract_prices(text).get('subItemPrice') or []

    seqs = Counter(it.get('count') for it in subs)
    print(f'items={len(subs)}  distinct count values={len(seqs)}')
    print(f'count values: {sorted(k for k in seqs if isinstance(k, int))}')
    dup = {k: v for k, v in seqs.items() if v > 1}
    print(f'repeated count values: {dup or "none"}')
    dup_price = Counter(round(it.get("unitPrice") or 0, 2) for it in subs)
    print(f'repeated unit prices : '
          f'{ {k: v for k, v in dup_price.items() if v > 1} or "none"}')
    if expected:
        got = {k for k in seqs if isinstance(k, int)}
        missing = [i for i in range(1, expected + 1) if i not in got]
        print(f'\nmissing 序号 1..{expected}: {missing}')


if __name__ == '__main__':
    main()
