# Windows 桌面版部署指南（星易查）

在 Windows 上免 Python、免命令行使用星易查。两种分发形式，功能完全一致：

| 形式 | 文件 | 适用 |
|------|------|------|
| 安装包 | `XingYiCha-Setup.exe`（Release 页）/<br>`星易查-Setup.exe`（Actions 产物） | 双击安装，桌面快捷方式，带卸载程序 |
| 便携版 | `XingYiCha-portable.zip`（Release 页）/<br>`星易查-便携版.zip`（Actions 产物） | 解压即用，U 盘拷贝、内网离线机 |

> 说明：GitHub Release 附件不支持中文文件名（会被截断），所以 Release 页面
> 上是 ASCII 名（`XingYiCha-*`），内容与 Actions 产物中的中文名完全一致。

## 一、获取安装包（云端构建，无需 Windows 机器）

1. 打开 GitHub 仓库 → **Actions** 标签页 → 左侧 **Windows 构建打包**
2. 点右侧 **Run workflow** → 分支选 `main` → 点绿色按钮
3. 等待约 15-20 分钟构建完成（绿色 ✓）
4. 点进本次运行，页面底部 **Artifacts** 区域下载 `星易查-Windows` 压缩包，
   解压得到 `星易查-Setup.exe` 与 `星易查-便携版.zip`
   （Release 页面则为 ASCII 名 `XingYiCha-*`）

> 打 tag（如 `v1.0.0`）再 push，会自动创建 GitHub Release 并把两个文件挂在
> Release 页面上，方便长期分发。
>
> 私有仓库使用 GitHub 免费额度（每月 2000 分钟，Windows 按 2 倍计费，
> 一次构建约消耗 30-40 分钟额度）。

## 二、安装与使用

**安装包版**：双击 `XingYiCha-Setup.exe`（或中文名 `星易查-Setup.exe`）→ 一路下一步（可勾选创建桌面快捷方式）→
完成页勾选"立即启动"或双击桌面图标。

**便携版**：解压 zip 到任意可写目录 → 双击 `星易查.exe`。

启动后**没有控制台窗口**，会直接打开默认浏览器（`http://127.0.0.1:5001`），
并在**任务栏右下角出现托盘图标**（星易查的角标）——它就是程序的"存在形式"，
与 macOS 的 Dock 图标一样：

| 想做的事 | 怎么做 |
|---|---|
| 打开/重新打开界面 | 双击托盘角标，或右键 → **打开页面**；也可以再双击一次桌面图标（会拉起已在运行的那一份，不会起第二个服务） |
| 误关了浏览器标签 | 同上——**关掉浏览器不会停止服务**，后台一直在跑 |
| 打开历史/上传/日志目录 | 右键角标 → **打开数据目录** |
| 退出星易查 | 右键角标 → **退出星易查**（会停服务并落盘日志） |

> 托盘角标默认收在右下角"隐藏的图标"里（Windows 的常见行为），把它拖到
> 任务栏常驻即可随时看到。
>
> 万一托盘起不来（依赖缺失/被安全软件拦截），程序会**自动回退到控制台窗口
> 模式**（即旧的"关窗即停服"形态）并弹框告知——不会留下一个看不见也停不掉的
> 后台进程。

历史记录与上传文件保存在 `%LOCALAPPDATA%\星易查\`，卸载重装不丢数据；
运行日志在 `%LOCALAPPDATA%\星易查\logs\xingyicha.log`（排障时把这个文件
发给维护方；程序异常退出时也会弹框提示日志位置）。

> **⚠️ 前置条件（仅当标书含老格式 `.doc`）**：`.docx` / `.pdf` / `.txt` /
> `.xlsx` / 扫描件 OCR 均开箱即用；`.doc` 的**正文提取**需先安装
> [LibreOffice](https://www.libreoffice.org/)（免费，官网下载安装包，一路
> 下一步即可，装好后重启星易查生效）。未安装时 `.doc` 正文自动跳过，
> 其元数据比对及全部其他格式、维度不受影响。
>
> LibreOffice **装在 D 盘等自定义目录也能自动识别**：程序按
> `SOFFICE_PATH` 环境变量 → PATH →
> `%ProgramFiles%` / `%ProgramFiles(x86)%` / `%LOCALAPPDATA%` 下的
> LibreOffice → 注册表 `HKLM\SOFTWARE\LibreOffice\UNO\InstallPath`
> （**安装包版**才写这个键，记的是你选的安装位置）依次探测，通常无需手动配置。
> **便携版/绿色版 LibreOffice**（解压即用、不写注册表）不在任何被探测的目录里，
> 需要设 `SOFFICE_PATH=D:\LibreOffice\program\soffice.exe`（也可指向安装
> 目录或 `program` 目录）再重启星易查。设了 `SOFFICE_PATH` 但指向的不是
> 可执行文件（数据文件、相对路径）时程序会记一条警告并回落自动探测。

## 三、功能完整性说明

| 功能 | Windows 表现 |
|------|-------------|
| .docx / .pdf / .txt / .xlsx | ✅ 完整支持 |
| 扫描件 PDF OCR | ✅ 完整支持（模型已打包进 exe） |
| .doc 元数据比对 | ✅ 完整支持 |
| .doc 正文提取 | ⚠️ 需另装 [LibreOffice](https://www.libreoffice.org/)（免费；常见安装位置与注册表记录的目录会自动识别，便携版请设 `SOFFICE_PATH`，见上）。未安装时自动跳过正文（若装了 antiword 会退回纯文本通道），其余维度不受影响；装好后重启星易查即可生效 |

如需让局域网其他电脑访问：设置环境变量 `HOST=0.0.0.0` 后启动
（首次会弹出 Windows 防火墙放行提示）。

## 四、环境变量（低配调优 / 行为微调）

程序全部行为参数走环境变量，默认值即开箱可用；仅在低配机器、大扫描件或
特殊需求时设置。完整参数表与选型建议见
[硬件配置要求](硬件配置要求.md)第七节。Windows 设置方法：

**临时（仅当次）**——在命令提示符（cmd）里设置后从同一窗口启动：

```bat
set OCR_MAX_PAGES=50
set OCR_TIME_BUDGET=120
"C:\Program Files\星易查\星易查.exe"
```

**永久（写入用户环境）**——`Win + R` 输入 `cmd` 回车，执行后**重启星易查**生效：

```bat
setx OCR_MAX_PAGES 50
setx PDF_TABLE_LAYOUT off
```

或图形界面：系统设置 → 「编辑系统环境变量」→ 环境变量 → 用户变量 → 新建。
常见用途速查：`OCR_MAX_PAGES`/`OCR_TIME_BUDGET`（限制扫描件 OCR 页数/时长）、
`PDF_TABLE_LAYOUT=off`（不加载表格版面模型，省约 110MB 内存）、
`EXTRACT_WORKERS=1`（内存极紧张时强制串行）、`MAX_CONTENT_LENGTH_MB`
（单次上传总量上限）、`SOFFICE_PATH`（LibreOffice 装在自定义目录时手动
指定 `soffice.exe` 或安装目录）。

## 五、常见问题

- **LibreOffice 装在 D 盘 / 自定义目录，星易查认不出来**：v2.3.0 及更早
  版本先查 `PATH`，再拿 `%ProgramFiles%` / `%ProgramFiles(x86)%` 两个默认
  目录兜底——而且这两个目录排在 antiword/catdoc **之后**，所以自定义目录
  确实会识别不到（表现为 `.doc` 正文提取为空、界面只提示"未提取到任何文本
  内容"，不会说缺 LibreOffice）。当前版本已支持：① 注册表
  `HKLM\SOFTWARE\LibreOffice\UNO\InstallPath`（安装在哪儿，安装包版就会
  把它记在这儿）；② `%LOCALAPPDATA%` 下的按用户安装；③ 环境变量
  `SOFFICE_PATH` 手动指定（可指向 `soffice.exe`、安装目录或 `program`
  目录）。装完/设完 **重启星易查**生效。确认方法：运行日志
  `%LOCALAPPDATA%\星易查\logs\xingyicha.log` 里有一行 `.doc 正文转换器: …`；
  在命令行窗口执行 `星易查.exe --check` 也会打印（会接回该窗口显示）。
- **单次上传总量超 1GB 报"上传文件过大"或"分析失败，请确认服务器已启动"**：
  v2.2.1 及更早版本的桌面版存在 waitress 服务器的 1GB 隐性上传上限（与
  "默认不限上传"的设计相悖），超限时浏览器可能显示上述两种报错之一。
  v2.2.2 已放宽至 32GB（设置 `MAX_CONTENT_LENGTH_MB` 后按其 2 倍限制，
  超限时返回带具体限额的明确提示）。
- **分析中途报 "network error"/"Failed to fetch"，控制台打印
  "Client disconnected"**：分析期间的长时间静默（多文件并行提取时，纯
  Word/文字版 PDF 批次要等每份文件提取完才有进度事件）会让带网络超时
  的浏览器或安全软件把这条"看似没有响应"的连接掐断。v2.2.3 起流式
  进度每 10 秒发一次心跳保持连接活跃，且服务器空闲超时对齐分析时长
  上限，已根治。旧版本缓解办法：用新版 Chrome/Edge（无内置请求超时）、
  减小单次文件总量以缩短静默窗口。
- **杀毒软件报毒/拦截**：PyInstaller 打包的 exe 无数字签名，部分杀软会误报。
  在杀软中将 `星易查.exe`（或安装目录）加入信任/白名单即可。代码开源可审计。
- **双击后提示端口占用**：程序会自动改用相邻端口（5002-5010）。实际地址
  看托盘角标的悬浮提示，或日志 `%LOCALAPPDATA%\星易查\logs\xingyicha.log`
  里的 `访问地址`（更省事的办法：再双击一次桌面图标，它会直接打开正确地址）。
- **想换端口**：`星易查.exe 5005`（带端口参数启动）。
- **上传文件在哪**：`%LOCALAPPDATA%\星易查\uploads`（分析完成后可清理）。
- **历史记录在哪**：`%LOCALAPPDATA%\星易查\history`。
- **换电脑 / 重装怎么迁移**：整个 `%LOCALAPPDATA%\星易查\` 目录拷贝到新机
  同路径即可（含历史记录与提取缓存；uploads 里是上传原件，介意体积可不拷）。

## 六、备选：本地 Windows 机器构建（云端不可用时）

在一台装了 Python 3.11 的 Windows 机器上，双击 `packaging\build_windows.bat`
即可完成与云端完全相同的构建（产物同样在 `dist\` 下）。生成安装包需另装
[Inno Setup 6](https://jrsoftware.org/isinfo.php)，只做便携版可跳过。

## 七、Docker 部署（服务器场景）

仍按仓库根目录 `docker-compose.yml` 使用，与桌面版互不影响。
