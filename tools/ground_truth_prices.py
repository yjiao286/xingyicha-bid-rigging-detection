# -*- coding: utf-8 -*-
"""Pull every price-bearing line from a bid PDF for ground-truth checks.

Only walks pages whose text mentions a pricing keyword, so it stays fast even
on 1000+ page / 200MB scans. Handy when a pricing fix needs to be validated
against what the document actually prints (the 2026-10 仪表管阀件 corpus was
fixed this way: each bidder's 分项报价表 was read off the PDF and compared with
`extract_prices()`'s sub-items; three of five then summed EXACTLY to the
declared 投标总价). Companion: `ground_truth_pages.py` dumps whole pages.

Usage: py -3.12 tools/ground_truth_prices.py <pdf> [more.pdf ...]
"""
import os
import re
import sys

import pymupdf

# Broken-xref PDFs make MuPDF print a repair diagnostic per damaged entry;
# it is console noise, not a failure (app.py silences it the same way).
try:
    pymupdf.TOOLS.mupdf_display_errors(False)
except Exception:  # noqa: BLE001 — older bindings lack the switch
    pass

KEYWORDS = ['开标一览', '综合报价表', '分项报价', '报价表', '投标总价', '报价一览',
            '投标函', '价格明细', '报价明细', '合计']
# lines worth printing: contain an amount-looking token
AMOUNT = re.compile(r'(\d[\d,]{2,}|\d+\.\d{2}|[壹贰叁肆伍陆柒捌玖拾佰仟万亿]{3,})')


def scan(path):
    doc = pymupdf.open(path)
    name = os.path.basename(path)
    print('#' * 100)
    print(f'# {name}   {len(doc)} pages')
    print('#' * 100)
    for i in range(len(doc)):
        try:
            text = doc[i].get_text()
        except Exception as exc:                       # noqa: BLE001
            print(f'  !! page {i+1} failed: {exc}')
            continue
        if not any(k in text for k in KEYWORDS):
            continue
        lines = [ln.strip() for ln in text.split('\n')]
        hits = [ln for ln in lines if AMOUNT.search(ln)]
        if not hits:
            continue
        print(f'--- page {i+1} ---')
        for ln in hits:
            print('   ', ln)
    doc.close()


if __name__ == '__main__':
    for p in sys.argv[1:]:
        scan(p)
