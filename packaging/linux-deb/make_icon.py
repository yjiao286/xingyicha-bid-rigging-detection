#!/usr/bin/env python3
"""构建期图标生成：static/img/logo.png → 256² PNG。

用法: make_icon.py <src_logo_png> <out_png>
PIL 来自已组装的 site-packages（pillow 是应用正式依赖）。
"""
import os
import sys

from PIL import Image  # noqa: E402

img = Image.open(sys.argv[1]).convert("RGBA")
os.makedirs(os.path.dirname(sys.argv[2]), exist_ok=True)
img.resize((256, 256), Image.LANCZOS).save(sys.argv[2])
print(f"  ✓ {sys.argv[2]} (256x256)")
