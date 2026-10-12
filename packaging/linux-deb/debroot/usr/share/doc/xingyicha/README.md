星易查 · 围串标风险识别分析系统（v3.1.0，银河麒麟适配构建）
================================================================

启动方式
  1. 开始菜单/桌面启动器：搜索或点击「星易查」
  2. 终端命令：xingyicha（等价于 /opt/xingyicha/run.sh）

  启动后自动打开浏览器访问 http://127.0.0.1:5001，
  关闭终端窗口即停止服务。

自定义
  XINGYICHA_PORT=6001 xingyicha   # 换端口
  XINGYICHA_DATA=~/xydata xingyicha  # 换数据目录（默认 ~/.xingyicha）

本包特性
  - 自带独立 Python 3.11 运行时与全部依赖，安装后离线可用
  - 针对 glibc 2.28+ 构建（银河麒麟 V10 SP1 / UOS / 主流发行版）
  - 安装时自动适配麒麟 KYSEC 执行控制（可信标签）

卸载
  sudo apt remove xingyicha     # 保留用户数据 ~/.xingyicha
  sudo apt purge xingyicha      # 连用户数据说明一并移除（数据仍保留）

输出为风险线索与核查建议，供人工复核，不构成违法认定结论。
