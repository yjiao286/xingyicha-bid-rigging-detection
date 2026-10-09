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
# 真值（人工读原文核对，2026-10-09）：
#   投标人K：序号 1-17 数据行 + 18 行售后服务 0 元（0 元行不计入分项），
#   行合计 = 合计行 = 5,910,000（旧解析 (名称,总价) 去重把序号 15/17 两行
#   同名同价的 40,000 误并成 16 项 5,870,000——此前的"真值"就是从那个
#   丢失行数的解析反推的，错了）。原件真正的不一致是 合计行 5,910,000
#   vs 投标一览表 5,900,000。
GT = {'6c2cc0bc': (5900000.0, 5910000.0),
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
