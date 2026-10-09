# -*- coding: utf-8 -*-
"""Dump the pricing section of a history record served by a live instance.

Usage: py -3.12 tools/dump_history_pricing.py <history_id> [port]
"""
import json
import sys
import urllib.request

def main():
    hid = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5001
    url = f'http://127.0.0.1:{port}/api/history/{hid}'
    with urllib.request.urlopen(url, timeout=120) as resp:
        rec = json.loads(resp.read().decode('utf-8'))
    pr = rec.get('pricing') or (rec.get('data') or {}).get('pricing') or {}
    print('history:', hid)
    print('project :', rec.get('project_name'))
    print('bids    :', rec.get('bid_files'))
    print()
    print('=== pricing.files ===')
    for f in pr.get('files') or []:
        print(json.dumps({k: f.get(k) for k in
                          ('name', 'totalPriceInTax', 'totalPrice', 'taxRate',
                           'bidRate', 'cost')}, ensure_ascii=False))
        for w in f.get('warnings') or []:
            print('    WARN:', w)
        subs = f.get('subItemPrice') or []
        print(f'    subItems: {len(subs)}')
        for it in subs[:40]:
            print(f'      count={it.get("count")!s:>6} unit={it.get("unitPrice")!s:>10} '
                  f'{str(it.get("priceName"))[:70]}')
        if len(subs) > 40:
            print(f'      ... (+{len(subs) - 40} more)')
        print()
    print('=== pricing.findings ===')
    for x in pr.get('findings') or []:
        print('  -', x)


if __name__ == '__main__':
    main()
