#!/usr/bin/env bash
# ── 星易查 银河麒麟 V10 适配 .deb 一键构建 ──────────────────────
# 产物：dist/xingyicha_<版本>-<修订>_amd64.deb
#
# 为什么不用 CI 的 PyInstaller 产物：CI 在 ubuntu-22.04（glibc 2.35）构建，
# _internal 库需要 GLIBC_2.34，而银河麒麟 V10 SP1 是 glibc 2.31，直接跑不起来。
# 本脚本改用 python-build-standalone（glibc 2.17+）+ manylinux≤2.28 wheel
# （glibc ≥2.28 即可），在麒麟上原生兼容。
#
# 为什么 deb 里只放一个 payload.tar.xz：dpkg 安装时对每个文件 fsync +
# KYSEC 逐文件处理，1 万个文件要 4-5 分钟；payload 方案 dpkg 只碰几个文件，
# postinst 里 tar 解包（约 25 秒）+ 只给百余个可执行文件打可信标签（约 3 秒），
# 全程 1 分钟内。
#
# 用法：
#   ./build-deb.sh [修订号]        # 默认 1，版本号取自 app.py APP_VERSION
#   DEB_REV=6 ./build-deb.sh       # 等价
#   XINGYICHA_DEB_CACHE=~/cache ./build-deb.sh   # 自定义缓存目录
set -euo pipefail

DEB_REV="${1:-${DEB_REV:-1}}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/packaging/linux-deb"
CACHE="${XINGYICHA_DEB_CACHE:-$ROOT/build/cache/deb}"
DIST="$ROOT/dist"
WHEELHOUSE="$CACHE/wheelhouse"

PY_VERSION="3.11.15"
PBS_TAG="20260623"
PY_TRIPLET="x86_64-unknown-linux-gnu"
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/cpython-${PY_VERSION}%2B${PBS_TAG}-${PY_TRIPLET}-install_only.tar.gz"
# GitHub 直连不通时依次回退的国内镜像
PBS_MIRRORS=("https://ghfast.top" "https://gh-proxy.com" "https://ghproxy.net")
PYPI_MIRRORS=("https://pypi.tuna.tsinghua.edu.cn/simple" "https://mirrors.aliyun.com/pypi/simple/" "https://pypi.org/simple")
ANTIWORD_POOLS=("https://mirrors.tuna.tsinghua.edu.cn/debian/pool/main/a/antiword/" "http://ftp.debian.org/debian/pool/main/a/antiword/")

APP_VERSION=$(sed -n "s/^APP_VERSION = '\([^']*\)'.*/\1/p" "$ROOT/app.py" | head -1)
[ -n "$APP_VERSION" ] || { echo "✗ 无法从 app.py 解析 APP_VERSION"; exit 1; }
DEB_VERSION="${APP_VERSION}-${DEB_REV}"
SITE_REL="python/lib/python3.11/site-packages"

log() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()  { printf '  \033[32m✓\033[0m %s\n' "$*"; }

mkdir -p "$CACHE" "$DIST" "$WHEELHOUSE"

# ── 1. 可重定位 CPython ───────────────────────────────────────
log "准备 CPython ${PY_VERSION}（python-build-standalone）"
PY_TARBALL="$CACHE/cpython-x86_64.tar.gz"
if [ ! -x "$CACHE/python/bin/python3" ]; then
  if [ ! -f "$PY_TARBALL" ]; then
    curl -fsSL --retry 3 -o "$PY_TARBALL" "$PBS_URL" \
      || for m in "${PBS_MIRRORS[@]}"; do
             echo "  直连失败，改走镜像 $m"
             curl -fsSL --retry 3 -o "$PY_TARBALL" "$m/$PBS_URL" && break
           done
  fi
  rm -rf "$CACHE/python" "$CACHE/.py-extract"
  mkdir -p "$CACHE/.py-extract"
  tar -xzf "$PY_TARBALL" -C "$CACHE/.py-extract"
  mv "$CACHE/.py-extract/python" "$CACHE/python"
  rm -rf "$CACHE/.py-extract"
fi
PY="$CACHE/python/bin/python3"
"$PY" --version | grep -q "$PY_VERSION" || { echo "✗ 缓存的 Python 版本异常"; exit 1; }
ok "Python $PY_VERSION 就绪: $PY"

# ── 2. 依赖 wheel ────────────────────────────────────────────
log "准备依赖 wheel（manylinux ≤2.28，麒麟 glibc 2.31 兼容）"
PYSTRAY_JUNK=(pystray python_xlib)   # 托盘不走 pystray，避免误入包
if [ -z "$(ls -A "$WHEELHOUSE" 2>/dev/null | grep -v -e pystray -e python_xlib)" ]; then
  DL_OK=0
  for idx in "${!PYPI_MIRRORS[@]}"; do
    echo "  源: ${PYPI_MIRRORS[$idx]}"
    if "$PY" -m pip download \
        --platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 \
        --platform manylinux2014_x86_64 \
        --python-version 311 --abi cp311 --implementation cp \
        --only-binary=:all: \
        -i "${PYPI_MIRRORS[$idx]}" --dest "$WHEELHOUSE" \
        -r "$HERE/requirements-deb.txt"; then
      DL_OK=1; break
    fi
  done
  [ "$DL_OK" = 1 ] || { echo "✗ 所有 PyPI 源均失败"; exit 1; }
fi
WHEELS=$(ls "$WHEELHOUSE"/*.whl | grep -v -e pystray -e python_xlib | wc -l)
ok "wheelhouse: $WHEELS 个 wheel"

# ── 3. 组装应用树 ────────────────────────────────────────────
log "组装应用树"
PKG="$CACHE/pkg"
SITE="$PKG/$SITE_REL"
rm -rf "$PKG"
mkdir -p "$PKG/app" "$PKG/bin" "$PKG/share/antiword" "$CACHE/icontools"
# 可重定位 Python 本体先行（wheel 展开进它的 site-packages）
cp -a "$CACHE/python" "$PKG/python"

for w in "$WHEELHOUSE"/*.whl; do
  case "$(basename "$w")" in
    pystray-*|python_xlib-*) : ;;            # Linux 托盘不用 pystray，直接跳过
    *) unzip -o -q "$w" -d "$SITE" ;;
  esac
done

cp "$ROOT/app.py" "$PKG/app/app.py"
cp -R "$ROOT/templates" "$PKG/app/templates"
cp -R "$ROOT/static" "$PKG/app/static"
find "$PKG/app" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find "$PKG/app" -name '.DS_Store' -delete 2>/dev/null || true

# 裁剪：标准库 GUI/教学附件 + 类型存根 + 包内 tests + 字节码缓存（约 -2400 文件）
rm -rf "$PKG/python/lib/python3.11/idlelib" \
       "$PKG/python/lib/python3.11/tkinter" \
       "$PKG/python/lib/python3.11/turtledemo"
find "$SITE" -name '*.pyi' -type f -delete 2>/dev/null || true
find "$SITE" -maxdepth 4 -type d \( -name test -o -name tests \) \
     -exec rm -rf {} + 2>/dev/null || true
find "$PKG" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
ok "文件数: $(find "$PKG" | wc -l)"

# antiword（.doc 正文转换回退通道）
log "获取 antiword"
python3 "$HERE/fetch_antiword.py" "$PKG" "$CACHE" "${ANTIWORD_POOLS[@]}" \
  && chmod 755 "$PKG/bin/antiword" \
  && ok "antiword 二进制 + 映射文件" \
  || echo "  ⚠ antiword 获取失败：.doc 正文不可用（其余功能正常）"

# 启动器 / 托盘 / 图标
log "启动器 + 托盘 + 图标"
cp "$HERE/run.sh"   "$PKG/run.sh";   chmod 755 "$PKG/run.sh"
cp "$HERE/start.sh" "$PKG/start.sh"; chmod 755 "$PKG/start.sh"
cp "$HERE/tray.py"  "$PKG/bin/tray.py"; chmod 755 "$PKG/bin/tray.py"
# pillow 已随应用依赖进 site-packages，图标生成直接复用
PYTHONPATH="$SITE" "$PY" "$HERE/make_icon.py" "$ROOT/static/img/logo.png" \
  "$PKG/share/icons/xingyicha.png"
mkdir -p "$PKG/share/icons"
ok "run.sh + start.sh + tray.py + icon"

# 自检：关键 import + waitress 在位（-c 而非 stdin 脚本：麒麟 KYSEC 拦后者）
log "依赖自检"
PYTHONPATH="$SITE" "$PY" -c 'import flask, docx, pypdf, fitz, rapidocr_onnxruntime, openpyxl, onnxruntime, cv2, PIL, waitress; print("  ✓ 关键依赖（含 waitress/PIL）可导入")'

# ── 4. payload + deb ─────────────────────────────────────────
log "payload.tar.xz（xz 多线程）"
cp "$ROOT/LICENSE" "$PKG/LICENSE"
( cd "$PKG" && XZ_OPT="-T0 -3" tar -cJf "$DIST/.payload.tar.xz" . )
ok "payload: $(du -h "$DIST/.payload.tar.xz" | cut -f1)"

log "组装 debroot"
DEBROOT="$CACHE/debroot"
rm -rf "$DEBROOT"
mkdir -p "$DEBROOT/DEBIAN" "$DEBROOT/opt" \
         "$DEBROOT/usr/bin" \
         "$DEBROOT/usr/share/applications" \
         "$DEBROOT/usr/share/doc/xingyicha" \
         "$DEBROOT/usr/share/icons/hicolor/256x256/apps"
cp "$DIST/.payload.tar.xz" "$DEBROOT/opt/xingyicha.payload.tar.xz"
rm -f "$DIST/.payload.tar.xz"
sed "s/@VERSION@/$DEB_VERSION/" "$HERE/debroot/DEBIAN/control.in" > "$DEBROOT/DEBIAN/control"
for f in postinst prerm postrm; do
  cp "$HERE/debroot/DEBIAN/$f" "$DEBROOT/DEBIAN/$f"
  chmod 755 "$DEBROOT/DEBIAN/$f"
done
cp "$HERE/debroot/usr/share/applications/xingyicha.desktop" \
   "$DEBROOT/usr/share/applications/"
cp "$PKG/share/icons/xingyicha.png" \
   "$DEBROOT/usr/share/icons/hicolor/256x256/apps/xingyicha.png"
cp "$HERE/debroot/usr/share/doc/xingyicha/"* "$DEBROOT/usr/share/doc/xingyicha/" 2>/dev/null || true
ln -sf /opt/xingyicha/run.sh "$DEBROOT/usr/bin/xingyicha"
SIZE=$(du -sk "$DEBROOT/opt" "$DEBROOT/usr" | awk '{s+=$1} END {print s}')
if grep -q '^Installed-Size:' "$DEBROOT/DEBIAN/control"; then
  sed -i "s/^Installed-Size:.*/Installed-Size: $SIZE/" "$DEBROOT/DEBIAN/control"
else
  sed -i "/^Architecture:/a Installed-Size: $SIZE" "$DEBROOT/DEBIAN/control"
fi

log "dpkg-deb 构建"
DEB="$DIST/xingyicha_${DEB_VERSION}_amd64.deb"
dpkg-deb --build --root-owner-group -Zxz "$DEBROOT" "$DEB"
ok "产物: $DEB ($(du -h "$DEB" | cut -f1))"
echo ""
echo "完成。目标机安装：sudo apt install ./$DEB（约 1 分钟）"
