#!/usr/bin/env bash
# ── 星易查 启动器 (.deb 安装版，位于 /opt/xingyicha/run.sh) ──
# 启动内置 Python 运行 app.py，等待就绪后用默认浏览器打开前端。
# 目录结构可重定位：HERE 取本脚本所在目录，安装/便携两用。
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
# 内置 antiword 的映射文件（.doc 文本提取用，缺失时 antiword 也能靠编译默认路径）
[ -d "$HERE/share/antiword" ] && export ANTIWORDHOME="$HERE/share/antiword"
# 便携 Python 找到内置第三方库
export PYTHONPATH="$HERE/python/lib/python3.11/site-packages${PYTHONPATH:+:$PYTHONPATH}"
# 关键：本地回环直连，绕过任何系统 HTTP 代理（政企麒麟常见根因）
export no_proxy="127.0.0.1,localhost,${HOST}"
export NO_PROXY="$no_proxy"
# 浏览器对 localhost 也尽量不走代理
export http_proxy="" https_proxy=""

mkdir -p "$UPLOAD_FOLDER" "$HISTORY_DIR" "$DATA_DIR"

if [ ! -x "$PYTHON" ]; then
  echo "× 找不到内置 Python: $PYTHON"
  echo "  请确认安装完整，且本包对应你的 CPU 架构（x86_64）。"
  read -p "按回车关闭..." _; exit 1
fi

cleanup() {
  if [ -n "${TRAY_PID:-}" ] && kill -0 "$TRAY_PID" 2>/dev/null; then
    kill "$TRAY_PID" 2>/dev/null
    wait "$TRAY_PID" 2>/dev/null
  fi
  if [ -n "${SERVER_PID:-}" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null
    wait "$SERVER_PID" 2>/dev/null
  fi
}
trap cleanup EXIT INT TERM

open_browser() {
  local url="$1"
  xdg-open "$url" 2>/dev/null \
    || sensible-browser "$url" 2>/dev/null \
    || x-www-browser "$url" 2>/dev/null \
    || gio open "$url" 2>/dev/null \
    || true
}

clear 2>/dev/null || true
echo "╔══════════════════════════════════════════╗"
echo "║     星 易 查                             ║"
echo "║     围串标风险识别分析系统                ║"
echo "╚══════════════════════════════════════════╝"
echo "  地址: $URL"
echo "  日志: $LOG_FILE"
echo "  [注意] 关闭此窗口将停止服务"
echo ""

# 端口已被占用 → 多半是已有实例在跑，直接复用打开浏览器
if (exec 3<>"/dev/tcp/${HOST}/${PORT}") 2>/dev/null; then
  exec 3>&- 3<&-
  echo "检测到端口 $PORT 已被占用，尝试复用已有实例..."
  open_browser "$URL" 2>/dev/null || true
  read -p "按回车关闭本窗口（不会停止已运行的服务）..." _
  exit 0
fi

# 启动服务（stdout/stderr 同时进终端与日志文件）
"$PYTHON" "$HERE/app/app.py" "$PORT" 2>&1 | tee "$LOG_FILE" &
SERVER_PID=$!
# tee 在管道里，真正要等的是 app.py：记录其 PID
APP_PID=$(pgrep -f "$HERE/app/app.py $PORT" | head -1)
[ -n "$APP_PID" ] && SERVER_PID="$APP_PID"

# 系统托盘角标（麒麟 UKUI 等，StatusNotifierItem/AppIndicator 协议）：
# 菜单与 Windows/macOS 版对齐——打开页面 / 打开数据目录 / 退出星易查。
# 依赖系统 python3-gi + libappindicator3（麒麟预装；缺失时静默降级纯终端）。
TRAY_PID=""
if [ "${XINGYICHA_TRAY:-1}" = "1" ] && [ -n "${DISPLAY:-}" ] \
   && [ -x /usr/bin/python3 ] && [ -f "$HERE/bin/tray.py" ]; then
  # 托盘图标：包内 256px logo 拷到数据目录（AppIndicator 读绝对路径）
  TRAY_ICON="$DATA_DIR/tray-icon.png"
  [ -f "$TRAY_ICON" ] || cp "$HERE/share/icons/xingyicha.png" "$TRAY_ICON" 2>/dev/null || TRAY_ICON="$HERE/share/icons/xingyicha.png"
  /usr/bin/python3 "$HERE/bin/tray.py" "$URL" "$DATA_DIR" "$SERVER_PID" "$TRAY_ICON" \
    >/dev/null 2>&1 &
  TRAY_PID=$!
fi

# 等待就绪
READY=0
for i in $(seq 1 40); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo ""
    echo "× 服务进程已退出（可能是端口冲突或依赖缺失）。"
    echo "  最近日志（$LOG_FILE）："
    echo "  ----------------------------------------"
    tail -n 25 "$LOG_FILE" 2>/dev/null | sed 's/^/  /'
    echo "  ----------------------------------------"
    echo "  提示：若是端口被占，改端口启动：XINGYICHA_PORT=6001 /opt/xingyicha/run.sh"
    read -p "按回车关闭..." _
    exit 1
  fi
  if (exec 3<>"/dev/tcp/${HOST}/${PORT}") 2>/dev/null; then
    exec 3>&- 3<&-
    READY=1; break
  fi
  sleep 1
done

# 自检：本地直连拿首页，确认不是代理在返回结构化错误
echo "自检：本地直连 $URL ..."
PROBE=$(curl -s --noproxy '*' -m 5 -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null || echo "000")
if [ "$PROBE" = "200" ]; then
  echo "[OK] 服务就绪（HTTP 200），正在打开浏览器..."
elif [ "$PROBE" = "000" ]; then
  echo "[注意] 本地直连失败（$PROBE）。服务可能仍在初始化，或端口被拦截。"
  echo "    请稍候手动访问：$URL"
else
  echo "[注意] 本地直连返回 HTTP $PROBE（非 200）。"
  echo "    若页面显示 {\"error\":\"服务器内部错误\",\"_meta\":...}，那不是本程序产生，"
  echo "    多为系统/浏览器 HTTP 代理拦截。请在浏览器代理设置里放行 127.0.0.1 / localhost。"
  echo "    最近日志见：$LOG_FILE"
fi

open_browser "$URL" &

# 前台等待服务进程（关闭窗口即停止）
if kill -0 "$SERVER_PID" 2>/dev/null; then
  wait "$SERVER_PID"
fi
