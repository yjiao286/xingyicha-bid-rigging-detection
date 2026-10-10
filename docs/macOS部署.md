# macOS 桌面版部署指南（星易查）

功能与 Windows / Linux 桌面版完全一致。Apple Silicon (M 系列) 与 Intel 双架构：

| 架构 | dmg 安装包 | zip 便携版 |
|------|-----------|-----------|
| Apple Silicon (M1/M2/M3/M4) | `XingYiCha-macOS-arm64.dmg` | `XingYiCha-macOS-arm64.zip` |
| Intel | `XingYiCha-macOS-x86_64.dmg` | `XingYiCha-macOS-x86_64.zip` |

## 一、获取（云端构建，与 Windows 版同源）

1. 登录 GitHub（私有仓库需有权限的账号）
2. Actions 页 → **桌面版三平台构建** → Run workflow：不带参数的手动运行
   产物在 Artifacts 区（保留 1 天）；参数里填 `release_tag`（如 `v3.0.0`）
   则直传该 Release。或直接打 `v*` tag 自动构建并发布
3. Release 页面下载对应架构的 dmg 或 zip（文件名带版本号后缀，如
   `XingYiCha-macOS-arm64-3.0.0.dmg`）

## 二、安装与使用

**dmg 安装包**：双击 dmg → 把「星易查」拖入 Applications → 从启动台/访达打开。
首次打开若提示"无法验证开发者"（应用未签名上架 App Store，属正常）：

- 方法一：右键（或按住 Control 点击）图标 → 选「打开」→ 确认
- 方法二：系统设置 → 隐私与安全性 → 允许"星易查"

**zip 便携版**：解压出 `XingYiCha.app`，双击即可；首次打开同样按上述方法放行。
若提示"App 已损坏，建议移到废纸篓"（部分浏览器下载会附加隔离属性），终端执行
`xattr -cr /Applications/XingYiCha.app` 后再打开。

启动后自动打开浏览器访问 `http://127.0.0.1:5001`。应用在后台常驻：Dock 有
图标、菜单栏右侧有"星"状态项（详见第三节），**关掉浏览器不会停止服务**；
退出走菜单栏"星" → 退出星易查，或 Dock 右键图标 → 退出。再次双击 .app
不会起第二个服务，只会把已在运行的那份页面拉起来。

> **⚠️ 前置条件（仅当标书含老格式 `.doc`）**：`.docx` / `.pdf` / `.txt` /
> `.xlsx` / 扫描件 OCR 均开箱即用；`.doc` 的**正文提取**需先安装
> LibreOffice（`brew install --cask libreoffice`，或
> [官网](https://www.libreoffice.org/) 下载 pkg 安装）。未安装时 `.doc`
> 正文自动跳过，其元数据比对及全部其他格式、维度不受影响。
>
> 从 Finder 双击启动的应用继承的是系统最小 `PATH`（不含 Homebrew 的
> `/opt/homebrew/bin`），所以程序除 `PATH` 外还会显式探测
> `/Applications/LibreOffice.app`、`~/Applications/LibreOffice.app` 与
> Homebrew / `/usr/local` 下的 soffice——**正常安装（官网 pkg 或
> `brew install --cask`）无需任何额外配置**；装在别处时设
> `SOFFICE_PATH=/path/to/soffice`（或安装目录、`.app` 包路径）后重启即可。

## 三、macOS 桌面集成

星易查在 macOS 上不只是"开了个本地网页"，还有原生桌面行为：

- **Dock 图标**：应用运行期间 Dock 有图标；点按图标（或从 Finder 重新打开）
  会**再次拉起页面**——浏览器标签页误关后不必重启应用；
- **菜单栏状态项**：屏幕右上角有「星易查」菜单，提供 **打开页面**、
  **打开数据目录**（在 Finder 中打开 `~/Library/Application Support/星易查`，
  历史/上传/日志都在这里）与 **退出** 三个动作，不用回到终端窗口去关闭服务。

> v2.5.0 及更早的 dmg 装出来的 .app 因 PyInstaller `console=True` 被隐式打上
> `LSBackgroundOnly`（后台应用：不进 Dock、菜单栏状态项不可靠），v3.0.0 起
> 已在 `packaging/star.spec` 显式关闭。旧版本想就地修复：删掉
> `XingYiCha.app/Contents/Info.plist` 里的 `LSBackgroundOnly` 键再执行
> `codesign --force --deep --sign - /Applications/XingYiCha.app` 重签名即可。

## 四、功能说明

| 功能 | 表现 |
|------|------|
| .docx / .pdf / .txt / .xlsx / 扫描件 OCR | ✅ 完整支持 |
| .doc 元数据比对 | ✅ 完整支持 |
| .doc 正文 | ⚠️ 需安装 LibreOffice（`brew install --cask libreoffice` 或官网下载，任意安装位置均可识别），未装时自动跳过，其余不受影响 |

数据目录：`~/Library/Application Support/星易查/`（history 与 uploads）。

## 五、环境变量（低配调优 / 行为微调）

默认值即开箱可用，仅按需设置；完整参数表见
[硬件配置要求](硬件配置要求.md)第七节。`.app` 双击不经过终端，需带参数时
从终端启动内层可执行文件：

```bash
OCR_MAX_PAGES=50 /Applications/XingYiCha.app/Contents/MacOS/XingYiCha
```

## 六、常见问题

- **Dock 里没有图标 / 菜单栏没有"星"**：v2.5.0 及更早的 dmg 存在此问题
  （应用被打成"后台应用"，见第三节说明）——升级到 v3.0.0 及之后版本，或按
  第三节的方法就地修复已安装的那份。
- **双击 .app 后"闪退"，但浏览器打开了页面**：不是故障——5001 端口上已有
  一个星易查在应答（常见于本机同时跑着源码开发服务器 `python3 app.py`），
  桌面版按单实例设计直接拉起那份页面后退出。想用桌面版本体，先停掉占用
  5001 的进程（`lsof -ti:5001 | xargs kill -9`）再双击。
- **5001 被其他程序占用**：自动改用 5002-5010。再双击一次 .app 会打开
  正确地址（比翻日志省事）。
- **运行日志在哪**：`~/Library/Application Support/星易查/logs/xingyicha.log`
  ——Finder 双击启动没有控制台输出，这个文件是唯一排障入口；菜单栏"星" →
  **打开数据目录** 可直接定位到它。
- **上传文件 / 历史记录在哪**：`~/Library/Application Support/星易查/uploads`
  与 `.../history`；换机迁移整个 `~/Library/Application Support/星易查` 目录
  拷到新机同路径即可。
- **让局域网其他电脑访问**：
  `HOST=0.0.0.0 /Applications/XingYiCha.app/Contents/MacOS/XingYiCha` 启动
  （首次 macOS 会弹防火墙放行询问），他机访问 `http://<本机IP>:5001`。
- **换端口**：`/Applications/XingYiCha.app/Contents/MacOS/XingYiCha 5005`
  （带端口参数启动）。

永久生效可写入 `~/.zshrc`：`export PDF_TABLE_LAYOUT=off`（之后从终端启动；
仅影响终端启动的实例）。

## 六、常见问题

- **提示"已损坏，无法打开"**：多为 Gatekeeper 对未签名应用的拦截，执行
  `xattr -cr /Applications/星易查.app` 后重试。
- **端口占用**：自动改用 5002-5010，以终端打印的实际地址为准。
- **M 系列跑 x86_64 版**：Rosetta 可运行但慢，请优先下载 arm64 版。
- **换电脑 / 重装怎么迁移**：整个 `~/Library/Application Support/星易查/`
  目录拷到新机同路径。
