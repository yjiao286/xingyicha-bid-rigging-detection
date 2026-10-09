# -*- coding: utf-8 -*-
"""End-to-end re-analysis of the 2026-10-09 history corpus, pricing-focused.

Reproduces what run_full_analysis does for pricing: load each cached extraction,
call extract_prices, then build the same comparison structures the report uses,
and print the ground-truth cross-check.

Usage: py -3.12 tools/verify_corpus_pricing.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402

CACHE = r'C:\Users\aiden\AppData\Local\星易查\extract_cache'

# Ground truth read off the PDFs (开标一览表 / 投标函 / 表内合计)
DOCS = [
    ('4830a8bb', '投标人G-仪表管阀件采购_', 54267.0, 0,
     '报价表只有"含税单价限价"列（招标方限价），无投标单价'),
    ('71a0485a', '投标人E公司-仪表管阀件采购_', 25192.22, 64, '投标单价列，64 行合计=总价'),
    ('4bf6de49', '投标人L公司-仪表管阀件采购_', 39034.0, None,
     '限价+投标单价双列；投标函 39034 / 开标一览表 39026（原件不一致）'),
    ('13a28e01', '投标人F-仪表管阀件采购_', 26603.59, 64, '管道段 18 行 + 续页 46 行'),
    ('6b972f82', '投标人H集团-仪表管阀件采购_', 38711.0, None,
     '投标函 38711（大写一致）；分项表 17 行价格在文本层为空'),
]


def main():
    ok = True
    for prefix, label, gt_total, gt_count, note in DOCS:
        name = next(n for n in os.listdir(CACHE) if n.startswith(prefix))
        with open(os.path.join(CACHE, name), encoding='utf-8') as f:
            text = json.load(f)['t']
        r = app.extract_prices(text)
        subs = r.get('subItemPrice') or []
        usum = sum(it.get('unitPrice') or 0 for it in subs)

        checks = []
        if r['totalPriceInTax'] is None or abs(r['totalPriceInTax'] - gt_total) > 0.01:
            checks.append(f'总价 {r["totalPriceInTax"]} != 真值 {gt_total}')
        if gt_count is not None and len(subs) != gt_count:
            checks.append(f'分项数 {len(subs)} != 真值 {gt_count}')
        # 分项单价合计只在与总价同一口径时才该相等（单价之和 = 总价）。
        # 投标人G gt_count=0：其报价表只有限价列、没有投标单价，0 项才正确。
        if gt_count and abs(usum - gt_total) > 0.02:
            checks.append(f'分项单价合计 {usum:.2f} != 总价 {gt_total}')
        if len(subs) > 64:
            checks.append(f'分项数 {len(subs)} 超过表格行数 64（多出的是幻觉行）')
        # no extracted value may exceed the declared total by an order of magnitude
        for it in subs:
            for k in ('unitPrice', 'totalPrice', 'totalPriceInTax'):
                v = it.get(k)
                if v is not None and v > gt_total * 10:
                    checks.append(f'{k}={v} 明显超量级（{it["priceName"][:24]}）')
                    break
        if r.get('cost') is not None:
            checks.append(f'成本被填充为 {r["cost"]}（本语料无成本项）')

        status = 'OK ' if not checks else 'BAD'
        if checks:
            ok = False
        print(f'[{status}] {label}')
        print(f'        总价 {r["totalPriceInTax"]}  (真值 {gt_total})   不含税 {r["totalPrice"]}   税率 {r["taxRate"]}')
        print(f'        分项 {len(subs)} 项   单价合计 {usum:.2f}   成本 {r["cost"]}')
        print(f'        真值依据：{note}')
        for w in r.get('warnings') or []:
            print(f'        WARN: {w}')
        for c in checks:
            print(f'        !! {c}')
        print()
    print('ALL OK' if ok else 'FAILURES PRESENT')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
