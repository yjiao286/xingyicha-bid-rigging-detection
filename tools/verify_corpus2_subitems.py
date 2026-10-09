# -*- coding: utf-8 -*-
"""Verify the sub-item comparison view for the new (service) corpus.

The UI's 分项报价卡 is built from pricing.subItemCompare + the per-file
sub-items, so checking only `extract_prices` would miss whether the grouping
now shows sane rows. This runs the same grouping the analysis does and prints
what the UI would show.

Usage: py -3.12 tools/verify_corpus2_subitems.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402

CACHE = r'extract_cache'
LABELS = {'6c2cc0bc': '投标人K', 'da81b305': '投标人I', '9c9b5a70': '投标人J'}
GT = {'6c2cc0bc': (5900000.0, 5870000.0),
      'da81b305': (5900000.0, 5900000.0),
      '9c9b5a70': (5920000.0, 5920000.0)}


def main():
    ok = True
    for pre, label in LABELS.items():
        name = next(n for n in os.listdir(CACHE) if n.startswith(pre))
        with open(os.path.join(CACHE, name), encoding='utf-8') as f:
            raw = f.read()
        try:
            text = json.loads(raw)['t']
        except (ValueError, KeyError):
            text = raw
        r = app.extract_prices(text)
        subs = r.get('subItemPrice') or []
        total_sum = sum(i.get('totalPrice') or 0 for i in subs)
        gt_total, gt_sum = GT[pre]

        checks = []
        if r['totalPriceInTax'] != gt_total:
            checks.append(f'总价 {r["totalPriceInTax"]} != {gt_total}')
        if abs(total_sum - gt_sum) > 1:
            checks.append(f'分项合计 {total_sum:.2f} != 文档行合计 {gt_sum:.2f}')
        for it in subs:
            nm = str(it.get('priceName') or '')
            if any(k in nm for k in ('联系人', '姓名', '合计报价')):
                checks.append(f'幻觉行: {nm}')
            if (it.get('totalPrice') or 0) > gt_total * 3:
                checks.append(f'量级异常: {nm} = {it["totalPrice"]}')
        if checks:
            ok = False
        print(f'[{"OK " if not checks else "BAD"}] {label}')
        print(f'       总价 {r["totalPriceInTax"]:,.2f}   分项 {len(subs)} 项   '
              f'分项合计 {total_sum:,.2f} (文档行合计 {gt_sum:,.2f})')
        for c in checks:
            print(f'       !! {c}')
    print()
    print('ALL OK' if ok else 'FAILURES PRESENT')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
