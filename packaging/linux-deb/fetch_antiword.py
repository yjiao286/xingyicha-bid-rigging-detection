#!/usr/bin/env python3
"""从 Debian 源抽取 antiword 二进制与映射文件（.doc 正文转换回退通道）。

用法: fetch_antiword.py <pkg_dir> <cache_dir> <pool_url>...
  pkg_dir  : 应用树根（bin/antiword 与 share/antiword/* 落在这里）
  cache_dir: .deb 缓存目录
  pool_url : Debian pool 地址（依次尝试，tuna 镜像在前）

成功退出 0；失败退出非 0（构建脚本据此降级，不阻断）。
"""
import io
import os
import re
import sys
import tarfile
import urllib.request

PKG, CACHE = sys.argv[1], sys.argv[2]
POOLS = sys.argv[3:]
os.makedirs(CACHE, exist_ok=True)
os.makedirs(os.path.join(PKG, 'bin'), exist_ok=True)
os.makedirs(os.path.join(PKG, 'share', 'antiword'), exist_ok=True)


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "xingyicha-deb-build/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


deb_path = None
for pool in POOLS:
    try:
        listing = http_get(pool).decode("latin1", "replace")
        names = sorted(re.findall(r'href="(antiword_[^"]*_amd64\.deb)"', listing))
        if not names:
            continue
        deb_path = os.path.join(CACHE, "antiword_" + names[-1])
        if not os.path.exists(deb_path):
            with open(deb_path, "wb") as f:
                f.write(http_get(pool + names[-1]))
        break
    except Exception as exc:
        print(f"  源 {pool} 失败: {exc}", file=sys.stderr)
if deb_path is None:
    sys.exit("antiword deb 获取失败（所有源均不可用）")

# deb = ar 归档；data.tar.* 里有 usr/bin/antiword 与 usr/share/antiword/*
raw = open(deb_path, "rb").read()
assert raw[:8] == b"!<arch>\n", "非 deb 归档"
members, off = {}, 8
while off < len(raw):
    hdr = raw[off:off + 60]
    name = hdr[0:16].decode().strip()
    size = int(hdr[48:58].decode().strip())
    members[name.rstrip("/")] = raw[off + 60:off + 60 + size]
    off += 60 + size + (size % 2)
data = members.get("data.tar.xz") or members.get("data.tar.gz") or members.get("data.tar.zst")
assert data, "deb 中无 data.tar"
tf = tarfile.open(fileobj=io.BytesIO(data))
want_bin = re.compile(r"^\./?usr/bin/antiword$")
want_map = re.compile(r"^\./?usr/share/antiword/[^/]+$")
n_bin = n_map = 0
for m in tf.getmembers():
    if want_bin.match(m.name):
        with open(os.path.join(PKG, "bin", "antiword"), "wb") as f:
            f.write(tf.extractfile(m).read())
        n_bin += 1
    elif want_map.match(m.name):
        with open(os.path.join(PKG, "share", "antiword", os.path.basename(m.name)), "wb") as f:
            f.write(tf.extractfile(m).read())
        n_map += 1
assert n_bin == 1, f"antiword 二进制抽取异常 (n={n_bin})"
print(f"  ✓ antiword 二进制 + {n_map} 个映射文件")
