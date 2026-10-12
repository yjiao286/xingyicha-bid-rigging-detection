#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""星易查系统托盘助手（银河麒麟 UKUI / 麒麟系 Linux 适配）。

用系统自带的 python3-gi + libappindicator3（StatusNotifierItem 协议）实现与
Windows/macOS 版对齐的托盘角标：

  打开页面      → xdg-open 前端地址（菜单首项，加粗默认）
  打开数据目录  → xdg-open ~/.xingyicha（上传/历史/日志所在）
  退出星易查    → SIGTERM 停服务进程 → 日志由 run.sh 落盘 → 托盘退出

设计为独立小进程：不随应用捆绑任何 GUI 依赖，缺失 python3-gi /
libappindicator3 的发行版上自动退出（静默降级为纯终端模式），应用本体不受影响。

用法: tray.py <url> <data_dir> <server_pid> <icon_png>
"""
import os
import signal
import subprocess
import sys

import gi

gi.require_version('AppIndicator3', '0.1')
gi.require_version('Gtk', '3.0')
from gi.repository import AppIndicator3, GLib, Gtk  # noqa: E402

URL, DATA_DIR, SERVER_PID, ICON = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]


def server_alive():
    try:
        os.kill(SERVER_PID, 0)
        return True
    except OSError:
        return False


def open_url(*_a):
    subprocess.Popen(['xdg-open', URL])


def open_dir(*_a):
    subprocess.Popen(['xdg-open', DATA_DIR])


def quit_app(*_a):
    # 与关闭终端窗口同等的停止方式：SIGTERM 服务进程；
    # run.sh 的 wait 返回后负责收尾，本进程随后自行退出。
    try:
        os.kill(SERVER_PID, signal.SIGTERM)
    except OSError:
        pass
    Gtk.main_quit()


menu = Gtk.Menu()

item_open = Gtk.MenuItem(label='打开页面')
item_open.connect('activate', open_url)
item_open.show()
menu.append(item_open)

item_data = Gtk.MenuItem(label='打开数据目录')
item_data.connect('activate', open_dir)
item_data.show()
menu.append(item_data)

menu.append(Gtk.SeparatorMenuItem())

item_quit = Gtk.MenuItem(label='退出星易查')
item_quit.connect('activate', quit_app)
item_quit.show()
menu.append(item_quit)

indicator = AppIndicator3.Indicator.new(
    'xingyicha', ICON, AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
indicator.set_title('星易查 · 围串标风险识别（%s）' % URL)
indicator.set_menu(menu)


def watchdog(*_a):
    """服务进程不在了（崩溃/被关/已退出）→ 撤下角标并退出，不留孤儿图标。"""
    if not server_alive():
        Gtk.main_quit()
        return False
    return True


GLib.timeout_add_seconds(2, watchdog)

if not server_alive():
    sys.exit(0)
Gtk.main()
