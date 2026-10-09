# -*- coding: utf-8 -*-
"""Print the specific pricing pages of a bid PDF, with full page text.

Usage: py -3.12 tools/ground_truth_pages.py <pdf> <page[,page...]>   # 1-based
"""
import sys

import pymupdf

if __name__ == '__main__':
    path = sys.argv[1]
    pages = []
    for chunk in sys.argv[2:]:
        for part in chunk.split(','):
            part = part.strip()
            if part:
                pages.append(int(part))
    doc = pymupdf.open(path)
    for p in pages:
        print('=' * 34, f'PAGE {p}', '=' * 34)
        print(doc[p - 1].get_text())
    doc.close()
