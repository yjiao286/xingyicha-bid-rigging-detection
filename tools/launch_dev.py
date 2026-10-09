#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星易查 — 工作区（测试）启动器。

开发用的一键启动器：跑**当前工作区源码**（app.py），而不是 `Program Files`
里那个已安装的桌面版。用途是让改动后的代码能被立刻验证——桌面版打包要重新
构建才会带上新代码。

它做四件事：
  1. 校验依赖，缺什么直接说清楚（含 pip 安装命令），不留下半死不活的进程；
  2. 自己挑端口：先探 127.0.0.1 的候选端口，把空闲的那个**显式**传给
     app.py。必须显式传——app.py 内部也会顺延端口（5001 被占用就换 5002），
     但那是它私有的，启动器无从得知用户最终该开哪个地址；
  3. 起服务（与桌面版同一条启动路径：`app.py <port>`）；
  4. 轮询 /api/ping，**确认监听成功之后**才开浏览器，并把地址打进控制台。

数据目录与桌面版一致（非冻结态仍用 `%LOCALAPPDATA%\\星易查`），所以历史
记录与提取缓存两边共享：桌面版分析过的东西在这里能直接复看，反之亦然。
两者可以同时运行——端口不同即可（桌面版占 5001，本启动器自动顺延）。

用法：
    py -3.12 tools/launch_dev.py [--port 5001] [--no-browser]
环境变量：
    DEV_PORT          首选端口（默认 5001）
    DEV_NO_BROWSER=1  不自动开浏览器
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP = REPO / 'app.py'

# (import 名, pip 名) —— app.py 顶层的硬依赖，缺一个就直接起不来
REQUIRED = [
    ('flask', 'flask'),
    ('docx', 'python-docx'),
    ('pypdf', 'pypdf'),
    ('olefile', 'olefile'),
    ('openpyxl', 'openpyxl'),
    ('pymupdf', 'pymupdf'),
]
# 可选：缺了只降级，不阻断（与 app.py 的降级路径一致）
OPTIONAL = [
    ('rapidocr_onnxruntime', 'rapidocr-onnxruntime', '扫描件 / docx 内嵌图片 OCR'),
    ('numpy', 'numpy', 'OCR 运行时依赖'),
    ('cv2', 'opencv-python', 'OCR 运行时依赖'),
]

BANNER = '=' * 66


def _force_utf8_console():
    """Make this script's own stdout/stderr survive Chinese text.

    Windows consoles are frequently cp1252/cp936, where printing the banner
    raises UnicodeEncodeError and kills the launcher before it starts
    anything. The child (app.py) is already covered by PYTHONIOENCODING in
    its env; this covers the launcher itself. Python 3.7+ only.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError, OSError):
            pass


def _port_free(host, port):
    """True when nothing is listening on host:port (and it is bindable)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _pick_port(host, preferred, span=10):
    for cand in range(preferred, preferred + span):
        if _port_free(host, cand):
            return cand, (cand != preferred)
    return None, False


def _app_version():
    """Read APP_VERSION out of app.py without importing it.

    Importing app.py executes the whole module (Flask app construction,
    converter discovery, cache setup) just to print a version string.
    """
    try:
        for line in APP.read_text(encoding='utf-8').splitlines():
            if line.startswith('APP_VERSION'):
                return line.split('=', 1)[1].strip().strip('\'"')
    except OSError:
        pass
    return '?'


def _check_deps():
    missing_hard, missing_soft = [], []
    for mod, pip_name in REQUIRED:
        try:
            __import__(mod)
        except ImportError:
            missing_hard.append((mod, pip_name))
    for mod, pip_name, why in OPTIONAL:
        try:
            __import__(mod)
        except ImportError:
            missing_soft.append((mod, pip_name, why))
    return missing_hard, missing_soft


def _wait_ready(host, port, timeout=120.0):
    """Poll /api/ping until the server answers. Returns the URL or None.

    The timeout is generous because a cold start imports pymupdf (and, when
    installed, the ~50MB pymupdf-layout model) before the listener opens.
    """
    url = f'http://{host}:{port}'
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + '/api/ping', timeout=2) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode('utf-8', 'replace'))
                    if body.get('app') == 'xingyicha':
                        return url
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(0.4)
    return None


def _announce(url, version):
    print(BANNER)
    print(f'  就绪  v{version}  {url}')
    print('  数据目录与桌面版共用（历史记录 / 提取缓存互相可见）')
    print('  停止：在本窗口按 Ctrl+C')
    print(BANNER)


def main():
    _force_utf8_console()
    ap = argparse.ArgumentParser(description='星易查 工作区（测试）启动器')
    ap.add_argument('--port', type=int,
                    default=int(os.environ.get('DEV_PORT', '5001')),
                    help='首选端口（默认 5001，被占用则顺延）')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--no-browser', action='store_true',
                    default=os.environ.get('DEV_NO_BROWSER') == '1')
    args = ap.parse_args()

    os.chdir(REPO)
    if not APP.is_file():
        print(f'[x] 找不到 {APP}')
        return 2
    version = _app_version()

    print(BANNER)
    print(f'  星易查 · 工作区测试启动器   (app.py v{version})')
    print(f'  代码目录: {REPO}')
    print(BANNER)

    missing_hard, missing_soft = _check_deps()
    if missing_hard:
        print('[x] 缺少必需依赖，无法启动：')
        for mod, pip_name in missing_hard:
            print(f'      {mod}  (pip 包: {pip_name})')
        print('\n    安装： py -3.12 -m pip install ' +
              ' '.join(p for _, p in missing_hard))
        return 3
    for mod, pip_name, why in missing_soft:
        print(f'[!] 可选依赖缺失: {mod} ({pip_name}) — {why}将不可用')

    port, shifted = _pick_port(args.host, args.port)
    if port is None:
        print(f'[x] {args.host} 的 {args.port}-{args.port + 9} 端口全部被占用，无法启动')
        return 4
    if shifted:
        print(f'[i] 端口 {args.port} 已被占用（桌面版在跑？），改用 {port}')

    env = dict(os.environ)
    env['HOST'] = args.host
    env['PORT'] = str(port)
    env['PYTHONIOENCODING'] = 'utf-8'      # 中文横幅在 GBK 控制台不炸
    env['PYTHONUNBUFFERED'] = '1'

    # 显式传端口：app.py 内部还会再顺延一次，但那样启动器就不知道真实地址了。
    proc = subprocess.Popen([sys.executable, str(APP), str(port)], env=env)

    ready = [None]

    def _probe():
        ready[0] = _wait_ready(args.host, port)

    t = threading.Thread(target=_probe, daemon=True)
    t.start()
    t.join(timeout=125)

    if ready[0] is None:
        print('[x] 服务未在超时内就绪。上方 app.py 的输出是排障依据；')
        print('    若端口被占/依赖缺失，进程可能已自行退出。')
        if proc.poll() is None:
            proc.terminate()
        return 5

    _announce(ready[0], version)
    if not args.no_browser:
        try:
            webbrowser.open(ready[0])
        except Exception:  # noqa: BLE001 — a browser hiccup must not kill the server
            print(f'[i] 自动打开浏览器失败，请手动访问 {ready[0]}')

    try:
        return proc.wait()
    except KeyboardInterrupt:
        print('\n[i] 收到 Ctrl+C，正在停止…')
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 0


if __name__ == '__main__':
    sys.exit(main())
