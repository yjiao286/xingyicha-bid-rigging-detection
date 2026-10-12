#!/usr/bin/env bash
# ── 星易查 桌面静默启动器（开始菜单/桌面双击入口，无终端窗口）──
# 后台拉起服务 + 托盘角标，就绪后打开浏览器，本脚本随即退出；
# 应用生命周期由托盘菜单「退出星易查」管理（对齐 Windows/macOS 版）。
# 终端排障模式请用 /usr/bin/xingyicha（run.sh，可见日志窗口）。
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$HERE/python/bin/python3"
PORT="${XINGYICHA_PORT:-5001}"
HOST="${XINGYICHA_HOST:-127.0.0.1}"
URL="http://${HOST}:${PORT}"
DATA_DIR="${XINGYICHA_DATA:-$HOME/.xingyicha}"
LOG_FILE="$DATA_DIR/server.log"

export UPLOAD_FOLDER="$DATA_DIR/uploads"
export HISTORY_DIR="$DATA_DIR/history"
export PATH="$HERE/bin:$PATH"
export HOST
[ -d "$HERE/share/antiword" ] && export ANTIWORDHOME="$HERE/share/antiword"
export PYTHONPATH="$HERE/python/lib/python3.11/site-packages${PYTHONPATH:+:$PYTHONPATH}"
# 本地回环直连，绕过系统 HTTP 代理（政企麒麟常见）
export no_proxy="127.0.0.1,localhost,${HOST}" NO_PROXY="127.0.0.1,localhost,${HOST}"
unset http_proxy https_proxy 2>/dev/null || true

mkdir -p "$UPLOAD_FOLDER" "$HISTORY_DIR" "$DATA_DIR"

# 已有实例在跑：直接打开页面（托盘退出/关终端可停旧实例）
if curl -s --noproxy '*' -m 2 -o /dev/null "$URL" 2>/dev/null; then
  xdg-open "$URL" 2>/dev/null \
    || sensible-browser "$URL" 2>/dev/null \
    || gio open "$URL" 2>/dev/null || true
  exit 0
fi

# 后台服务：setsid 脱离会话（桌面入口进程退出后不受影响），日志落文件
setsid "$PYTHON" "$HERE/app/app.py" "$PORT" >>"$LOG_FILE" 2>&1 </dev/null &
APP_PID=$!

# 托盘角标（系统 python3-gi + libappindicator；缺失时静默跳过）
if [ "${XINGYICHA_TRAY:-1}" = "1" ] && [ -n "${DISPLAY:-}" ] \
   && [ -x /usr/bin/python3 ] && [ -f "$HERE/bin/tray.py" ]; then
  TRAY_ICON="$DATA_DIR/tray-icon.png"
  [ -f "$TRAY_ICON" ] || cp "$HERE/share/icons/xingyicha.png" "$TRAY_ICON" 2>/dev/null \
    || TRAY_ICON="$HERE/share/icons/xingyicha.png"
  setsid /usr/bin/python3 "$HERE/bin/tray.py" "$URL" "$DATA_DIR" "$APP_PID" "$TRAY_ICON" \
    >>"$LOG_FILE" 2>&1 </dev/null &
fi

# 等服务就绪后开浏览器（最多 40 秒），随后本脚本退出
for i in $(seq 1 40); do
  curl -s --noproxy '*' -m 2 -o /dev/null "$URL" 2>/dev/null && break
  kill -0 "$APP_PID" 2>/dev/null || exit 1
  sleep 1
done
xdg-open "$URL" 2>/dev/null \
  || sensible-browser "$URL" 2>/dev/null \
  || x-www-browser "$URL" 2>/dev/null \
  || gio open "$URL" 2>/dev/null || true
exit 0
