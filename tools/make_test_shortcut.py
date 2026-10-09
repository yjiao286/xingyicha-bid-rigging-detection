#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在桌面创建一个"星易查 测试版"图标，双击即启动**工作区源码**做测试。

为什么需要脚本而不是直接建快捷方式：`WScript.Shell`（COM）写 .lnk 时把路径
按**系统 ANSI 代码页**转换，本机 ACP=1252，于是任何含中文的路径都会被拒绝
（'Value does not fall within the expected range'）——而本仓库路径恰好含
『星易查』。绕法是写 **8.3 短名**（`C:\\Users\\aiden\\...\\7F8A~1\\XINGYI~1`）：
纯 ASCII，COM 接受，Windows 解析时仍指向同一目录（显示名仍是长名）。

脚本会在运行时解析短名，所以换机器/换目录后重跑即可。若目标卷禁用了 8.3
名生成（`fsutil 8dot3name query`），脚本会退化为在 `%LOCALAPPDATA%` 下建一条
ASCII 路径的目录联接（junction），快捷方式指向联接——两条路都是纯 ASCII。

用法：
    py -3.12 tools/make_test_shortcut.py            # 创建/刷新
    py -3.12 tools/make_test_shortcut.py --remove   # 删除
"""
import argparse
import ctypes
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LAUNCHER = REPO / '启动测试版.bat'
LNK_NAME = '星易查 测试版.lnk'
JUNCTION = Path(os.environ.get('LOCALAPPDATA', '')) / 'XingYiChaDev'
ICON_SRC = Path(r'C:\Program Files (x86)\星易查\_internal\star.ico')

PS_CREATE = r'''# -*- coding: utf-8 -*-
param(
    [Parameter(Mandatory=$true)][string]$Lnk,
    [Parameter(Mandatory=$true)][string]$Target,
    [Parameter(Mandatory=$true)][string]$WorkDir,
    [string]$Icon = '',
    [string]$Desc = ''
)
$ErrorActionPreference = 'Stop'
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($Lnk)
$s.TargetPath = $Target
$s.WorkingDirectory = $WorkDir
if ($Icon -and (Test-Path -LiteralPath $Icon)) { $s.IconLocation = "$Icon,0" }
$s.Description = $Desc
$s.Save()
$v = $sh.CreateShortcut($Lnk)
Write-Output ('TARGET=' + $v.TargetPath)
Write-Output ('WORKDIR=' + $v.WorkingDirectory)
Write-Output ('ICON=' + $v.IconLocation)
'''


def _run_ps_script(body, params):
    """Run a PowerShell script with clean argument binding.

    Why a temp .ps1 instead of `powershell -Command <text> -Foo bar`:
    -Command does not bind a `param()` block the way -File does, and any
    argument containing parentheses (the icon lives under 'Program Files
    (x86)') gets re-parsed as PowerShell syntax and blows up.

    The temp file is written as UTF-8 **with BOM**: Windows PowerShell 5.1
    reads .ps1 as ANSI unless a BOM is present, and this script carries
    Chinese text (the .lnk name and the description).
    """
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.ps1', prefix='xycha_lnk_')
    os.close(fd)
    try:
        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write(body)
        cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
               '-File', path]
        for k, v in params.items():
            cmd += [f'-{k}', str(v)]
        return subprocess.run(cmd, capture_output=True, text=True)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _short_path(p):
    """8.3 short (ASCII) form of a path, or None when unavailable."""
    try:
        GetShort = ctypes.windll.kernel32.GetShortPathNameW
        buf = ctypes.create_unicode_buffer(1024)
        n = GetShort(str(p), buf, 1024)
        if n and buf.value and buf.value != str(p):
            return buf.value
    except Exception:  # noqa: BLE001 — not Windows / API missing
        return None
    return None


def _is_ascii(s):
    try:
        s.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False


def _ensure_junction():
    """ASCII path pointing at the repo, for systems without 8.3 names."""
    if JUNCTION.exists():
        return JUNCTION
    JUNCTION.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(['cmd', '/c', 'mklink', '/J', str(JUNCTION), str(REPO)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f'[x] 目录联接创建失败: {r.stdout.strip()} {r.stderr.strip()}')
        return None
    print(f'[i] 已创建目录联接: {JUNCTION} -> {REPO}')
    return JUNCTION


def _desktop():
    """Desktop directory — ask the shell so OneDrive redirection is respected."""
    try:
        import ctypes.wintypes as wt
        CSIDL_DESKTOPDIRECTORY = 0x0010
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOPDIRECTORY,
                                                  None, 0, buf) == 0 and buf.value:
            return Path(buf.value)
    except Exception:  # noqa: BLE001
        pass
    return Path(os.environ.get('USERPROFILE', '')) / 'Desktop'


def remove(lnk):
    if lnk.exists():
        lnk.unlink()
        print(f'[i] 已删除 {lnk}')
    else:
        print(f'[i] 不存在: {lnk}')
    return 0


def main():
    ap = argparse.ArgumentParser(description='创建工作区测试版桌面图标')
    ap.add_argument('--remove', action='store_true', help='删除图标')
    args = ap.parse_args()

    if sys.platform != 'win32':
        print('[x] 本脚本用于 Windows（桌面 .lnk）。其他平台请直接跑 '
              'tools/launch_dev.py')
        return 2

    lnk = _desktop() / LNK_NAME
    if args.remove:
        return remove(lnk)

    if not LAUNCHER.is_file():
        print(f'[x] 找不到启动脚本 {LAUNCHER}')
        return 2

    # 解析一套纯 ASCII 的目标/工作目录
    target = _short_path(LAUNCHER)
    workdir = _short_path(REPO)
    if not (target and _is_ascii(target)) or not (workdir and _is_ascii(workdir)):
        print('[i] 本卷没有可用的 8.3 短名，改用目录联接')
        j = _ensure_junction()
        if j is None:
            return 3
        target = str(j / LAUNCHER.name)
        workdir = str(j)
        if not Path(target).is_file():
            print(f'[x] 联接目标不可用: {target}')
            return 3

    print(f'[i] 目标   : {target}')
    print(f'[i] 工作目录: {workdir}')

    # COM 的 CreateShortcut 同样按 ANSI 解释 .lnk 路径：中文名会被写成
    # '??? ???.lnk' 并抛 FileNotFoundException。所以先用 ASCII 临时名建好，
    # 再用 Python（原生 Unicode 路径）改名到最终的中文名。
    tmp_lnk = lnk.with_name(lnk.stem.encode('ascii', 'ignore').decode() or 'xycha')
    tmp_lnk = tmp_lnk.with_name('__xycha_test_tmp.lnk')

    r = _run_ps_script(PS_CREATE, {
        'Lnk': str(tmp_lnk),
        'Target': target,
        'WorkDir': workdir,
        'Icon': str(ICON_SRC),
        'Desc': '星易查 工作区测试版 — 启动当前源码 (app.py)，自动选端口并打开浏览器',
    })
    out = (r.stdout or '') + (r.stderr or '')
    if r.returncode != 0 or 'TARGET=' not in out or not tmp_lnk.is_file():
        print('[x] 创建快捷方式失败：')
        print(out.strip())
        try:
            tmp_lnk.unlink()
        except OSError:
            pass
        return 4

    os.replace(tmp_lnk, lnk)      # same directory -> atomic rename

    for line in out.strip().splitlines():
        print(f'    {line}')
    print(f'\n[OK] 桌面图标已就绪: {lnk}')
    print('     双击即启动工作区源码（自动挑端口，就绪后开浏览器）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
